# src/ingest.py
import sqlite3
import requests
from bs4 import BeautifulSoup
from src.db import get_connection

def extract_landing_page_text(url: str) -> str:
    """
    Fetches raw HTML from a target startup URL, strips out non-content tags,
    and returns sanitized body text.
    """
    # Ensure URL has a scheme
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Strip out non-content markup noise
        for element in soup(["script", "style", "nav", "footer", "noscript", "svg", "header"]):
            element.decompose()

        # Extract readable text and normalize whitespace
        raw_text = soup.get_text(separator=" ")
        cleaned_text = " ".join(raw_text.split())

        # Truncate to first 3,000 characters to keep downstream processing efficient
        return cleaned_text[:3000]

    except requests.RequestException as e:
        print(f"[!] Scraping Error for {url}: {e}")
        return ""

