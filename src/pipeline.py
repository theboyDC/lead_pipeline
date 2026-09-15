"""Orchestrates the full lead pipeline: discover -> enrich -> transform -> load.

Usage:
    python -m src.pipeline [--limit N] [--queries "q1" "q2" ...]
"""
import argparse
import logging
import time
from pathlib import Path

from src import config, enrich, extract_places, load, transform
from src.db import get_collection

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "pipeline.log"),
            logging.StreamHandler(),
        ],
    )


def run(queries: list[str], limit: int | None) -> dict:
    logger = logging.getLogger(__name__)
    collection = get_collection()

    seen_place_ids: set[str] = set()
    seen_domains: set[str] = set()
    stats = {
        "discovered": 0,
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
        "skipped_duplicate_domain": 0,
    }

    for query in queries:
        try:
            places = extract_places.search_places(query)
        except extract_places.PlacesAPIError:
            logger.exception("search failed for query=%r", query)
            stats["errors"] += 1
            continue

        time.sleep(config.LOCATIONIQ_MIN_SECONDS_BETWEEN_CALLS)

        for place in places:
            place_id = place.get("place_id")
            if not place_id or place_id in seen_place_ids:
                continue
            seen_place_ids.add(place_id)
            stats["discovered"] += 1

            if limit and stats["processed"] >= limit:
                logger.info("reached --limit=%d, stopping", limit)
                return stats

            try:
                details = extract_places.normalize_place(place)
                website = details.get("website")
                domain = transform.extract_domain(website)
                if domain and domain in seen_domains:
                    logger.info(
                        "skipping duplicate domain=%s (place_id=%s), already captured this run",
                        domain,
                        place_id,
                    )
                    stats["skipped_duplicate_domain"] += 1
                    continue
                enrichment = enrich.enrich_from_website(website) if website else {}
                if not enrichment.get("email"):
                    enrichment["email"] = details.get("email")
                record = transform.build_record(details, enrichment, place_id, query)
                is_new = load.upsert_startup(collection, record)
                if domain:
                    seen_domains.add(domain)
                stats["inserted" if is_new else "updated"] += 1
                stats["processed"] += 1
            except Exception:
                logger.exception("failed to process place_id=%s", place_id)
                stats["errors"] += 1

            time.sleep(0.5)  # be polite to target websites when scraping

    logger.info("pipeline finished: %s", stats)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None, help="max number of places to process"
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        default=config.SEARCH_QUERIES,
        help="override the default search queries",
    )
    return parser.parse_args()


if __name__ == "__main__":
    setup_logging()
    args = parse_args()
    run(args.queries, args.limit)
