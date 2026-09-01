-- Weather ETL Pipeline schema
-- Two normalized tables: a city can have many readings, so city
-- metadata is stored once and referenced by foreign key.

CREATE TABLE IF NOT EXISTS cities (
    city_id     SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    country     VARCHAR(100),
    latitude    NUMERIC(9,6) NOT NULL,
    longitude   NUMERIC(9,6) NOT NULL,
    UNIQUE (latitude, longitude)
);

CREATE TABLE IF NOT EXISTS readings (
    reading_id      SERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(city_id),
    recorded_at     TIMESTAMP NOT NULL,
    temperature_c   NUMERIC(5,2),
    humidity_pct    NUMERIC(5,2),
    wind_speed_kmh  NUMERIC(5,2),
    weather_code    INTEGER,
    ingested_at     TIMESTAMP DEFAULT NOW(),
    UNIQUE (city_id, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_readings_city_time
    ON readings (city_id, recorded_at);
