# Weather ETL Pipeline

A small end-to-end data engineering project: it **extracts** hourly weather
data from the free [Open-Meteo](https://open-meteo.com/) API, **transforms**
and cleans it with pandas, and **loads** it into a normalized PostgreSQL
database. Built as a portfolio project to demonstrate fit for a Data
Engineering elective.

## Why this project

It touches the core of a real data engineering workflow without needing any
paid tools or API keys:

- **Extract** — calling a REST API with `requests`, handling failures gracefully
- **Transform** — cleaning and reshaping JSON into tabular data with `pandas`
- **Load** — inserting into a normalized relational schema in PostgreSQL, with
  deduplication handled at the database level
- **Automation** — designed to be run on a schedule (`cron`) so it builds up a
  real historical dataset over time
- **Data quality** — basic validation, null-handling, and sanity bounds on
  incoming data

## Architecture

```
 ┌────────────────┐      ┌────────────────┐      ┌──────────────────┐
 │  Open-Meteo API │ ---> │  extract.py     │ ---> │  raw JSON (dict)  │
 └────────────────┘      └────────────────┘      └──────────────────┘
                                                            │
                                                            v
                                                  ┌──────────────────┐
                                                  │  transform.py     │
                                                  │  (pandas cleaning)│
                                                  └──────────────────┘
                                                            │
                                                            v
                                                  ┌──────────────────┐
                                                  │  load.py          │
                                                  │  (psycopg2 insert)│
                                                  └──────────────────┘
                                                            │
                                                            v
                                                  ┌──────────────────┐
                                                  │  PostgreSQL        │
                                                  │  cities / readings  │
                                                  └──────────────────┘
```

`pipeline.py` orchestrates all three stages and logs the outcome of each run
to `logs/pipeline.log`.

## Database schema

Two normalized tables — one city can have many readings, so city metadata
isn't repeated on every row (see `db/schema.sql`):

- **cities** `(city_id, name, country, latitude, longitude)`
- **readings** `(reading_id, city_id, recorded_at, temperature_c, humidity_pct, wind_speed_kmh, weather_code, ingested_at)`

A `UNIQUE (city_id, recorded_at)` constraint on `readings` prevents duplicate
inserts if the pipeline is accidentally run twice for the same hour.

## Project structure

```
weather-etl-pipeline/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml
├── db/
│   └── schema.sql
├── src/
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   ├── pipeline.py
│   └── db.py
├── notebooks/
│   └── exploration.ipynb
├── logs/
│   └── .gitkeep
└── tests/
    └── test_transform.py
```

## Setup

1. **Clone and install dependencies**

   ```bash
   git clone <your-repo-url>
   cd weather-etl-pipeline
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL** (via Docker, easiest option)

   ```bash
   docker compose up -d
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   # edit .env if you changed any DB credentials in docker-compose.yml
   ```

4. **Create the schema**

   ```bash
   docker exec -i weather-postgres psql -U weather_user -d weather_db < db/schema.sql
   ```

5. **Run the pipeline**

   ```bash
   python src/pipeline.py
   ```

6. **(Optional) Schedule it hourly with cron**

   ```
   0 * * * * cd /path/to/weather-etl-pipeline && venv/bin/python src/pipeline.py >> logs/pipeline.log 2>&1
   ```

## Running tests

```bash
pytest tests/
```

## Design decisions worth noting

- **PostgreSQL over SQLite** — chosen to demonstrate a client-server relational
  database with proper concurrency handling, rather than a single-file DB.
- **`ON CONFLICT DO NOTHING` for deduplication** — dedup logic lives at the
  database layer, not in application code, so it holds even if the pipeline
  is triggered manually or twice.
- **Every stage logs row counts and errors** — a pipeline that fails silently
  is a liability; logging is a small step toward observability.
- **Each stage (extract/transform/load) is a separate module** — keeps the
  pipeline testable in isolation and mirrors how orchestration tools like
  Airflow treat pipeline stages as discrete tasks.

## Possible next steps

- Replace the hardcoded city list with a `cities` config table
- Swap `cron` for Apache Airflow with a proper DAG
- Add a Streamlit dashboard for visualizing temperature trends over time
- Containerize the pipeline itself (not just Postgres) with Docker
