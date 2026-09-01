"""
Extract stage: pulls hourly weather data from the Open-Meteo API
for a fixed list of cities. No API key required.
"""

import requests
import logging

logger = logging.getLogger(__name__)

# Hardcoded for now — could later move to a config file or DB table
CITIES = [
    {"name": "Johannesburg", "country": "ZA", "lat": -26.2041, "lon": 28.0473},
    {"name": "Cape Town", "country": "ZA", "lat": -33.9249, "lon": 18.4241},
    {"name": "Nairobi", "country": "KE", "lat": -1.2921, "lon": 36.8219},
    {"name": "Lagos", "country": "NG", "lat": 6.5244, "lon": 3.3792},
]

BASE_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_city_weather(city: dict) -> dict | None:
    """
    Calls the Open-Meteo API for a single city and returns raw JSON.
    Returns None if the request fails, so the pipeline can skip
    a bad city instead of crashing the whole run.
    """
    params = {
        "latitude": city["lat"],
        "longitude": city["lon"],
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "timezone": "auto",
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()  # raises if status code is 4xx/5xx
        data = response.json()
        data["_city_meta"] = city  # attach our own metadata for later stages
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch weather for {city['name']}: {e}")
        return None


def extract_all() -> list[dict]:
    """
    Loops over all configured cities and collects raw API responses.
    Skips any city that failed rather than stopping the whole pipeline —
    this is a small data-quality/resilience decision worth mentioning
    in your write-up.
    """
    results = []
    for city in CITIES:
        logger.info(f"Fetching weather for {city['name']}...")
        raw = fetch_city_weather(city)
        if raw:
            results.append(raw)
    logger.info(f"Extracted data for {len(results)}/{len(CITIES)} cities")
    return results


if __name__ == "__main__":
    # Lets you run this file standalone to sanity-check the API call
    logging.basicConfig(level=logging.INFO)
    data = extract_all()
    print(data[0] if data else "No data extracted")
