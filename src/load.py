"""Persist a startup record into MongoDB, upserting on place_id."""
import logging

from pymongo.collection import Collection

logger = logging.getLogger(__name__)


def upsert_startup(collection: Collection, record: dict) -> bool:
    """Returns True if this was a new document, False if it updated an existing one."""
    result = collection.update_one(
        {"place_id": record["place_id"]}, {"$set": record}, upsert=True
    )
    is_new = result.upserted_id is not None
    logger.info(
        "%s %s (%s)",
        "inserted" if is_new else "updated",
        record.get("name"),
        record["place_id"],
    )
    return is_new
