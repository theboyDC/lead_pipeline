"""Pure functions that turn raw Places + scraped data into the unstructured
document we store in MongoDB. No network calls in this module."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = _WHITESPACE_RE.sub(" ", value).strip()
    return text or None


def normalize_phone(raw: str | None) -> str | None:
    """Best-effort normalization to a South African E.164-ish format."""
    if not raw:
        return None
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        return digits
    if digits.startswith("0"):
        return "+27" + digits[1:]
    if digits.startswith("27"):
        return "+" + digits
    return digits or None


def extract_domain(url: str | None) -> str | None:
    """Returns the bare registrable-ish domain (no scheme, no www) for dedup."""
    if not url:
        return None
    netloc = urlparse(url if "//" in url else f"//{url}").netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]
    return netloc or None


def score_lead(record: dict) -> int:
    """0-4 completeness score: one point each for phone, website, email, description."""
    contact = record.get("contact") or {}
    return sum(
        1
        for value in (contact.get("phone"), contact.get("website"), contact.get("email"), record.get("description"))
        if value
    )


def build_record(place_details: dict, enrichment: dict, place_id: str, search_query: str) -> dict:
    """Combine a normalized place result and website enrichment into one document."""
    geometry = place_details.get("geometry", {}).get("location", {})
    phone = place_details.get("international_phone_number") or place_details.get(
        "formatted_phone_number"
    )

    record = {
        "place_id": place_id,
        "name": clean_text(place_details.get("name")),
        "address": clean_text(place_details.get("formatted_address")),
        "location": {
            "lat": geometry.get("lat"),
            "lng": geometry.get("lng"),
        },
        "contact": {
            "phone": normalize_phone(phone),
            "website": place_details.get("website"),
            "email": enrichment.get("email"),
        },
        "description": clean_text(enrichment.get("description")),
        "types": place_details.get("types", []),
        "map_url": place_details.get("url"),
        "source_query": search_query,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    record["lead_score"] = score_lead(record)
    return record
