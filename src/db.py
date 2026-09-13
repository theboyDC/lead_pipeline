"""
Small helper module for creating a PostgreSQL connection.
Reads credentials from environment variables (loaded from .env via
python-dotenv), so no secrets are hardcoded in the codebase.
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """
    Returns a new psycopg2 connection using credentials from .env.
    Callers are responsible for closing the connection (or using it
    as a context manager).
    """
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "weather_db"),
        user=os.getenv("DB_USER", "weather_user"),
        password=os.getenv("DB_PASSWORD", "weather_pass"),
    )
