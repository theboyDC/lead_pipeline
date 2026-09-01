"""
Orchestrates the full ETL run: extract -> transform -> load.
This is the entry point you'd run manually, via cron, or eventually
hand off to an orchestrator like Airflow.
"""

import logging
import os
from datetime import datetime

from extract import extract_all
from transform import transform_all
from load import load_readings

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "pipeline.log")),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


def run_pipeline():
    start = datetime.now()
    logger.info("=== Pipeline run started ===")

    try:
        raw_records = extract_all()
        if not raw_records:
            logger.error("No data extracted — aborting run")
            return

        clean_df = transform_all(raw_records)
        if clean_df.empty:
            logger.error("Transform produced no clean rows — aborting run")
            return

        inserted = load_readings(clean_df)
        logger.info(f"Pipeline run complete. {inserted} new row(s) inserted.")

    except Exception as e:
        # Catch-all so a single bad run is logged clearly instead of
        # crashing silently under cron with no visible output.
        logger.exception(f"Pipeline run failed: {e}")

    finally:
        duration = (datetime.now() - start).total_seconds()
        logger.info(f"=== Pipeline run finished in {duration:.2f}s ===")


if __name__ == "__main__":
    run_pipeline()
