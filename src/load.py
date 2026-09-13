"""
Load stage: takes the cleaned DataFrame from transform.py and writes it
into PostgreSQL, following the normalized cities/readings schema.

For each row: look up (or insert) the city to get its city_id, then
insert the reading against that city_id. Duplicate readings for the
same city + timestamp are silently skipped via ON CONFLICT.
"""

import logging
import pandas as pd
from db import get_connection

logger = logging.getLogger(__name__)


def get_or_create_city(cur, city_name: str, country: str, lat: float, lon: float) -> int:
    """
    Looks up a city by its coordinates. If it doesn't exist yet, inserts it.
    Returns the city_id either way.
    """
    cur.execute(
        "SELECT city_id FROM cities WHERE latitude = %s AND longitude = %s",
        (lat, lon),
    )
    result = cur.fetchone()
    if result:
        return result[0]

    cur.execute(
        """
        INSERT INTO cities (name, country, latitude, longitude)
        VALUES (%s, %s, %s, %s)
        RETURNING city_id
        """,
        (city_name, country, lat, lon),
    )
    return cur.fetchone()[0]


def load_readings(df: pd.DataFrame) -> int:
    """
    Loads a cleaned DataFrame into the database.
    Returns the number of reading rows successfully inserted
    (duplicates that hit the unique constraint are not counted).
    """
    if df.empty:
        logger.warning("Nothing to load — DataFrame is empty")
        return 0

    inserted = 0
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for _, row in df.iterrows():
                    city_id = get_or_create_city(
                        cur,
                        row["city_name"],
                        row["country"],
                        float(row["latitude"]),
                        float(row["longitude"]),
                    )

                    cur.execute(
                        """
                        INSERT INTO readings
                            (city_id, recorded_at, temperature_c,
                             humidity_pct, wind_speed_kmh, weather_code)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (city_id, recorded_at) DO NOTHING
                        """,
                        (
                            city_id,
                            row["recorded_at"],
                            row["temperature_c"],
                            row["humidity_pct"],
                            row["wind_speed_kmh"],
                            int(row["weather_code"]) if pd.notna(row["weather_code"]) else None,
                        ),
                    )
                    # cur.rowcount is 1 if inserted, 0 if the conflict clause skipped it
                    inserted += cur.rowcount
    finally:
        conn.close()

    logger.info(f"Loaded {inserted} new reading(s) into the database")
    return inserted


if __name__ == "__main__":
    from extract import extract_all
    from transform import transform_all

    logging.basicConfig(level=logging.INFO)
    raw = extract_all()
    clean_df = transform_all(raw)
    load_readings(clean_df)
