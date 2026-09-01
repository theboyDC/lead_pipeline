"""
Basic unit tests for the transform stage.
Run with: pytest tests/
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from transform import transform_all


def make_raw_record(temperature=20.0, city_name="TestCity"):
    """Helper to build a fake Open-Meteo-shaped API response."""
    return {
        "_city_meta": {"name": city_name, "country": "ZZ", "lat": 0.0, "lon": 0.0},
        "current": {
            "time": "2026-09-01T12:00",
            "temperature_2m": temperature,
            "relative_humidity_2m": 55,
            "wind_speed_10m": 10.5,
            "weather_code": 1,
        },
    }


def test_transform_produces_expected_columns():
    df = transform_all([make_raw_record()])
    expected_cols = {
        "city_name", "country", "latitude", "longitude", "recorded_at",
        "temperature_c", "humidity_pct", "wind_speed_kmh", "weather_code",
    }
    assert expected_cols.issubset(set(df.columns))


def test_transform_drops_null_temperature():
    record = make_raw_record()
    record["current"]["temperature_2m"] = None
    df = transform_all([record])
    assert df.empty


def test_transform_drops_out_of_range_temperature():
    record = make_raw_record(temperature=200.0)  # impossible value
    df = transform_all([record])
    assert df.empty


def test_transform_handles_missing_key_gracefully():
    broken_record = {"_city_meta": {"name": "X", "country": "ZZ", "lat": 0, "lon": 0}}
    df = transform_all([broken_record])
    assert df.empty


def test_transform_keeps_valid_row():
    df = transform_all([make_raw_record(temperature=25.3)])
    assert len(df) == 1
    assert df.iloc[0]["temperature_c"] == 25.3
