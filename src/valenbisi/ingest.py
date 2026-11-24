import json
import os

from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import pg8000.native
import requests
from dotenv import load_dotenv

import logging
from pydantic import AwareDatetime, BaseModel, Field, ValidationError

import random
import time



API_URL = "https://api.citybik.es/v2/networks/valenbisi"
#API_URL = "http://127.0.0.1:9"

logger = logging.getLogger(__name__)
#import json
#estaciones = json.load(open("notebooks/snapshot_0.json", encoding="utf-8"))["network"]["stations"]
#lats = [s["latitude"] for s in estaciones if s["latitude"] is not None]
#lons = [s["longitude"] for s in estaciones if s["longitude"] is not None]
#print(min(lats), max(lats), min(lons), max(lons))

#39.439796 39.501413 -0.426354265293528 -0.323492 
LAT_MIN, LAT_MAX = 39.40, 39.55
LON_MIN, LON_MAX = -0.45, -0.30


MAX_ATTEMPTS = 4
BASE_DELAY_S = 2
TIMEOUT = (5, 15)  # (segundos para conectar, segundos para leer la respuesta)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

class StationRow(BaseModel):
    station_id: str
    name: str
    latitude: float = Field(ge=LAT_MIN, le=LAT_MAX)
    longitude: float = Field(ge=LON_MIN, le=LON_MAX)
    slots: int = Field(ge=0)
    observed_at: AwareDatetime  # exige fecha con zona horaria
    free_bikes: int = Field(ge=0)
    empty_slots: int = Field(ge=0)
    last_updated: str


def fetch() -> dict:
    """Llama a la API con reintentos y espera creciente ante errores pasajeros."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(API_URL, timeout=TIMEOUT)
            if response.status_code not in RETRYABLE_STATUS:
                response.raise_for_status()  # los 4xx fallan aquí, sin reintentar
                return response.json()
            error = f"HTTP {response.status_code}"
        except (requests.ConnectionError, requests.Timeout) as e:
            error = repr(e)

        if attempt == MAX_ATTEMPTS:
            raise RuntimeError(f"La API no respondió tras {MAX_ATTEMPTS} intentos: {error}")

        delay = BASE_DELAY_S * 2 ** (attempt - 1) + random.uniform(0, 1)
        logger.warning("Intento %d/%d falló (%s); reintento en %.1f s", attempt, MAX_ATTEMPTS, error, delay)
        time.sleep(delay)

def connect(database_url: str) -> pg8000.native.Connection:
    url = urlparse(database_url)
    return pg8000.native.Connection(
        user=unquote(url.username),
        password=unquote(url.password),
        host=url.hostname,
        port=url.port or 5432,
        database=url.path.lstrip("/"),
        ssl_context=True,
    )


def load(conn: pg8000.native.Connection, fetched_at: datetime, payload: dict, rows: list[dict]) -> int:
    """Guarda el crudo y, en una transacción aparte, las capas limpias.

    Devuelve cuántas filas nuevas entraron en station_status.
    """
    # 1. Crudo: se guarda siempre y primero, pase lo que pase después.
    conn.run(
        "INSERT INTO raw_snapshots (fetched_at, payload) "
        "VALUES (:fetched_at, CAST(:payload AS jsonb))",
        fetched_at=fetched_at,
        payload=json.dumps(payload),
    )

    if not rows:
        return 0
    rows_json = json.dumps(rows, default=str)

    # 2 y 3. Limpio: estaciones y estados, juntos o ninguno.
    conn.run("START TRANSACTION")
    try:
        conn.run(
            """
            INSERT INTO stations (station_id, name, latitude, longitude, slots, first_seen, last_seen)
            SELECT station_id, name, latitude, longitude, slots,
                   CAST(:seen_at AS timestamptz), CAST(:seen_at AS timestamptz)
            FROM jsonb_to_recordset(CAST(:rows AS jsonb))
                 AS r(station_id text, name text, latitude double precision,
                      longitude double precision, slots int)
            ON CONFLICT (station_id) DO UPDATE SET
                name       = EXCLUDED.name,
                latitude   = EXCLUDED.latitude,
                longitude  = EXCLUDED.longitude,
                slots      = EXCLUDED.slots,
                first_seen = LEAST(stations.first_seen, EXCLUDED.first_seen),
                last_seen  = GREATEST(stations.last_seen, EXCLUDED.last_seen)
            """,
            seen_at=fetched_at,
            rows=rows_json,
        )
        conn.run(
            """
            INSERT INTO station_status
                (station_id, observed_at, free_bikes, empty_slots, last_updated)
            SELECT station_id, observed_at, free_bikes, empty_slots, last_updated
            FROM jsonb_to_recordset(CAST(:rows AS jsonb))
                 AS r(station_id text, observed_at timestamptz,
                      free_bikes int, empty_slots int, last_updated text)
            ON CONFLICT (station_id, observed_at) DO NOTHING
            """,
            rows=rows_json,
        )
        inserted = conn.row_count  # filas realmente insertadas (las ignoradas no cuentan)
        conn.run("COMMIT")
    except Exception:
        conn.run("ROLLBACK")
        raise
    return inserted


def record_run(
    conn: pg8000.native.Connection,
    started_at: datetime,
    stations_total: int,
    rows_valid: int,
    rows_inserted: int,
    error: str | None,
) -> None:
    conn.run(
        "INSERT INTO ingest_runs "
        "(started_at, finished_at, status, stations_total, rows_valid, rows_inserted, error) "
        "VALUES (:started_at, now(), :status, :total, :valid, :inserted, :error)",
        started_at=started_at,
        status="error" if error else "ok",
        total=stations_total,
        valid=rows_valid,
        inserted=rows_inserted,
        error=error,
    )


def parse(payload: dict) -> list[dict]:
    """Convierte el JSON en filas validadas; las inválidas se descartan y se registran."""
    rows = []
    for s in payload["network"]["stations"]:
        extra = s.get("extra") or {}
        timestamp = s.get("timestamp")
        raw = {
            "station_id": s.get("id"),
            "name": s.get("name"),
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
            "slots": extra.get("slots"),
            "observed_at": timestamp.removesuffix("Z") if timestamp else None,
            "free_bikes": s.get("free_bikes"),
            "empty_slots": s.get("empty_slots"),
            "last_updated": extra.get("last_updated"),
        }
        try:
            rows.append(StationRow(**raw).model_dump())
        except ValidationError as e:
            problems = [(err["loc"][0], err["msg"]) for err in e.errors()]
            logger.warning("Estación descartada %s: %s", raw["station_id"], problems)
    return rows


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    database_url = os.environ["DATABASE_URL"]

    started_at = datetime.now(timezone.utc)
    stations_total = rows_valid = rows_inserted = 0
    error = None

    conn = connect(database_url)
    try:
        payload = fetch()
        fetched_at = datetime.now(timezone.utc)
        stations_total = len(payload["network"]["stations"])
        rows = parse(payload)
        rows_valid = len(rows)
        rows_inserted = load(conn, fetched_at, payload, rows)
    except Exception as e:
        error = repr(e)
        raise  # el workflow de GitHub debe seguir saliendo en rojo
    finally:
        try:
            record_run(conn, started_at, stations_total, rows_valid, rows_inserted, error)
        except Exception:
            logger.exception("No se pudo registrar la ejecución en ingest_runs")
        finally:
            conn.close()

    print(
        f"{started_at:%Y-%m-%d %H:%M:%S} UTC: {rows_valid} válidas de {stations_total}, "
        f"{rows_inserted} filas nuevas en station_status"
    )


if __name__ == "__main__":
    main()