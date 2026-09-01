"""
Transform stage: takes raw API JSON responses and reshapes them
into a clean pandas DataFrame matching the `readings` table schema.
"""

import pandas as pd
import logging

logger = logging.getLogger(__name__)


def transform_all(raw_records: list[dict]) -> pd.DataFrame:
    """
    Converts a list of raw Open-Meteo JSON responses into a tidy DataFrame
    with one row per city reading, ready for loading into Postgres.
    """
    rows = []

    for record in raw_records:
        try:
            city_meta = record["_city_meta"]
            current = record["current"]

            rows.append({
                "city_name": city_meta["name"],
                "country": city_meta["country"],
                "latitude": city_meta["lat"],
                "longitude": city_meta["lon"],
                "recorded_at": current["time"],
                "temperature_c": current.get("temperature_2m"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "weather_code": current.get("weather_code"),
            })
        except KeyError as e:
            # If the API response is missing a field we expect, log it
            # and skip that record rather than letting the whole
            # pipeline crash on one bad response.
            logger.warning(f"Skipping malformed record, missing key: {e}")
            continue

    df = pd.DataFrame(rows)

    if df.empty:
        logger.warning("Transform produced an empty DataFrame")
        return df

    # --- Cleaning steps ---
    # Convert recorded_at to a proper datetime type
    df["recorded_at"] = pd.to_datetime(df["recorded_at"])

    # Drop rows where the core measurement (temperature) is missing —
    # a reading with no temperature isn't useful for this dataset
    before = len(df)
    df = df.dropna(subset=["temperature_c"])
    dropped = before - len(df)
    if dropped:
        logger.info(f"Dropped {dropped} rows with missing temperature")

    # Basic sanity bounds — Open-Meteo shouldn't return these,
    # but defensive checks are a good data-quality habit
    df = df[(df["temperature_c"] > -60) & (df["temperature_c"] < 60)]

    logger.info(f"Transformed {len(df)} clean rows")
    return df


if __name__ == "__main__":
    from extract import extract_all
    logging.basicConfig(level=logging.INFO)
    raw = extract_all()
    clean_df = transform_all(raw)
    print(clean_df)
