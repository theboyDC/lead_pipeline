"""This file manages the SQLite connection lifecycle and schema initialization.
It uses sqlite3
Row to return rows as dictionary-like objects,
which simplifies working with data downstream."""



import sqlite3
import os

DB_NAME = "pipeline_data.db"

def get_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't already exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS founders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                website_url TEXT UNIQUE NOT NULL,
                founder_name TEXT DEFAULT 'Founder',
                linkedin_url TEXT,
                site_raw_text TEXT,
                pain_point TEXT,          -- Technical friction identified
                proposed_solution TEXT,   -- Specific backend code solution
                generated_pitch TEXT,     -- Tailored outreach message
                outreach_status TEXT DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
    
    
