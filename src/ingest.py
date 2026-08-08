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

def ingest_lead(company_name: str, website_url: str, founder_name: str = "Founder", linkedin_url: str = "") -> bool:
    """
    Extracts site content and writes a new lead record into SQLite.
    Prevents duplicate entries based on the UNIQUE website_url constraint.
    """
    print(f"[*] Ingesting: {company_name} ({website_url})...")
    site_text = extract_landing_page_text(website_url)

    if not site_text:
        print(f"[!] Warning: No text content extracted for {company_name}. Storing basic profile.")

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO founders (company_name, website_url, founder_name, linkedin_url, site_raw_text)
                VALUES (?, ?, ?, ?, ?)
            """, (company_name, website_url, founder_name, linkedin_url, site_text))
            conn.commit()
            print(f"[✓] Successfully ingested {company_name} into database!")
            return True
        except sqlite3.IntegrityError:
            print(f"[!] Duplicate skipped: {website_url} already exists in database.")
            return False
if __name__ == "__main__":
    # Test run script against a real website
    test_company = "Example Corp"
    test_url = "https://example.com"
    ingest_lead(test_company, test_url, "Jane Doe", "https://linkedin.com/in/janedoe")

