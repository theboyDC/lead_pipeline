"""MongoDB connection helpers."""
from pymongo import MongoClient
from pymongo.collection import Collection

from src import config

_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI)
    return _client


def get_collection() -> Collection:
    db = get_client()[config.MONGO_DB_NAME]
    collection = db[config.MONGO_COLLECTION]
    collection.create_index("place_id", unique=True)
    return collection
