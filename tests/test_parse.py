import json
from pathlib import Path

from valenbisi.ingest import parse

SNAPSHOT = Path(__file__).parent / "data" / "snapshot_0.json"


def load_payload() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_parse_real_snapshot():
    payload = load_payload()
    rows = parse(payload)

    assert len(rows) == len(payload["network"]["stations"])
    assert rows[0]["observed_at"].tzinfo is not None
    assert all(r["free_bikes"] >= 0 and r["empty_slots"] >= 0 for r in rows)


def test_parse_discards_station_with_missing_field():
    payload = load_payload()
    stations = payload["network"]["stations"]
    broken_id = stations[0]["id"]
    del stations[0]["free_bikes"]

    rows = parse(payload)

    assert len(rows) == len(stations) - 1
    assert broken_id not in {r["station_id"] for r in rows}