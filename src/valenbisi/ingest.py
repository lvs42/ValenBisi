import json
import os

from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import pg8000.native
import requests
from dotenv import load_dotenv


API_URL = "https://api.citybik.es/v2/networks/valenbisi"

def main():

    load_dotenv()
    database_url = os.environ["DATABASE_URL"]


    #llamada API_URL
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()
    payload = response.json()

    fetched_at = datetime.now(timezone.utc)


    url = urlparse(database_url)
    conn = pg8000.native.Connection(
        user=unquote(url.username),
        password=unquote(url.password),
        host=url.hostname,
        port=url.port or 5432,
        database=url.path.lstrip("/"),
        ssl_context=True,
    )

    try:
        conn.run(
            "INSERT INTO raw_snapshots (fetched_at, payload) "
            "VALUES (:fetched_at, CAST(:payload AS jsonb))",
            fetched_at=fetched_at,
            payload=json.dumps(payload),
        )
    finally:
        conn.close()

    print(f"{fetched_at:%Y-%m-%d %H:%M:%S} UTC: snapshot guardado")



if __name__ == "__main__":
    main()