CREATE TABLE IF NOT EXISTS raw_snapshots (
    fetched_at timestamptz NOT NULL,
    payload    jsonb       NOT NULL
);

CREATE TABLE IF NOT EXISTS stations (
    station_id text PRIMARY KEY NOT NULL,
    name text NOT NULL,
    latitude Float NOT NULL,
    longitude Float NOT NULL,
    first_seen timestamptz NOT NULL,
    last_seen timestamptz NOT NULL,
    slots INT NOT NULL
);


CREATE TABLE IF NOT EXISTS station_status(
    station_id text NOT NULL REFERENCES stations(station_id),
    observed_at timestamptz NOT NULL,
    PRIMARY KEY (station_id, observed_at),
    free_bikes INT NOT NULL,
    empty_slots INT NOT NULL,
    last_updated text  NOT NULL

);

/*"id": "00bb7d72809bca3d4398c311c8aa9074",
  "name": "_CALLE_JUAN_XXIII",
  "latitude": 39.492557,
  "longitude": -0.382803,
  "timestamp": "2026-11-16T12:33:51.730642+00:00Z",
  "free_bikes": 1,
  "empty_slots": 14,
  "extra": {
    "uid": "175",
    "renting": true,
    "returning": true,
    "last_updated": "2026-11-16T02:12:32",
    "address": "Juan XXIII - Domingo Gómez",
    "payment": [
      "creditcard"
    ],
    "payment-terminal": true,
    "slots": 15,
    "normal_bikes": 1,
    "virtual": false
  }
}

{
  "uid": "175",
  "renting": true,
  "returning": true,
  "last_updated": "2026-11-16T02:12:32",
  "address": "Juan XXIII - Domingo Gómez",
  "payment": [
    "creditcard"
  ],
  "payment-terminal": true,
  "slots": 15,
  "normal_bikes": 1,
  "virtual": false
  */

CREATE INDEX IF NOT EXISTS idx_station_status_observed_at
    ON station_status (observed_at);