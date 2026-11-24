-- Una fila por ejecución de la ingesta: primer dato de monitorización.
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at     timestamptz NOT NULL,
    finished_at    timestamptz NOT NULL,
    status         text        NOT NULL CHECK (status IN ('ok', 'error')),
    stations_total int         NOT NULL,   -- estaciones que trajo la API
    rows_valid     int         NOT NULL,   -- las que pasaron la validación
    rows_inserted  int         NOT NULL,   -- filas nuevas en station_status
    error          text
);

CREATE INDEX IF NOT EXISTS idx_ingest_runs_started_at ON ingest_runs (started_at);