"""Export stored leads from MongoDB to a flat CSV file for outreach/CRM use.

Usage:
    python -m src.export [--out leads.csv]
"""
import argparse
import csv
import logging
from pathlib import Path

from src.db import get_collection

logger = logging.getLogger(__name__)

CSV_FIELDS = [
    "name",
    "address",
    "lat",
    "lng",
    "phone",
    "website",
    "email",
    "description",
    "types",
    "map_url",
    "source_query",
    "scraped_at",
    "place_id",
    "lead_score",
]


def flatten_record(record: dict) -> dict:
    """Turn a nested MongoDB startup document into a flat dict of CSV columns."""
    location = record.get("location") or {}
    contact = record.get("contact") or {}
    return {
        "name": record.get("name"),
        "address": record.get("address"),
        "lat": location.get("lat"),
        "lng": location.get("lng"),
        "phone": contact.get("phone"),
        "website": contact.get("website"),
        "email": contact.get("email"),
        "description": record.get("description"),
        "types": ";".join(record.get("types") or []),
        "map_url": record.get("map_url"),
        "source_query": record.get("source_query"),
        "scraped_at": record.get("scraped_at"),
        "place_id": record.get("place_id"),
        "lead_score": record.get("lead_score"),
    }


def export_to_csv(records: list[dict], path: Path) -> int:
    """Writes records to a CSV file at path. Returns the number of rows written."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        count = 0
        for record in records:
            writer.writerow(flatten_record(record))
            count += 1
    return count


def run(out_path: Path) -> int:
    collection = get_collection()
    records = list(collection.find({}))
    count = export_to_csv(records, out_path)
    logger.info("exported %d leads to %s", count, out_path)
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("leads.csv"), help="output CSV file path"
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()
    run(args.out)
