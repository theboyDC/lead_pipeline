"""Central configuration for the Johannesburg tech-startup lead pipeline."""
import os

from dotenv import load_dotenv

load_dotenv()

LOCATIONIQ_API_KEY = os.getenv("LOCATIONIQ_API_KEY", "")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "jhb_tech_startups")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "startups")

# Greater Johannesburg centroid, used to build a bounding box for LocationIQ search.
JOHANNESBURG_CENTER = {"lat": -26.2041, "lng": 28.0473}
_LAT_DELTA = 0.27  # ~30km north/south
_LNG_DELTA = 0.30  # ~30km east/west at this latitude
# LocationIQ/Nominatim viewbox format: "min_lon,max_lat,max_lon,min_lat"
JOHANNESBURG_VIEWBOX = (
    f"{JOHANNESBURG_CENTER['lng'] - _LNG_DELTA},{JOHANNESBURG_CENTER['lat'] + _LAT_DELTA},"
    f"{JOHANNESBURG_CENTER['lng'] + _LNG_DELTA},{JOHANNESBURG_CENTER['lat'] - _LAT_DELTA}"
)

# Varied queries improve coverage: LocationIQ search returns a capped number
# of results per call (no pagination token like Google), so we spread the
# search across query terms and known JHB tech hubs instead of one broad query.
SEARCH_QUERIES = [
    "tech startup in Johannesburg",
    "software company in Johannesburg",
    "fintech company in Johannesburg",
    "IT company in Johannesburg",
    "technology company in Sandton",
    "tech company in Rosebank Johannesburg",
    "startup incubator Johannesburg",
    "tech company in Braamfontein Johannesburg",
]

REQUEST_TIMEOUT_SECONDS = 10
SCRAPE_USER_AGENT = "JHBTechLeadBot/1.0 (+contact: lead-pipeline maintainer)"

LOCATIONIQ_SEARCH_URL = "https://us1.locationiq.com/v1/search"
LOCATIONIQ_LOOKUP_URL = "https://us1.locationiq.com/v1/lookup"
LOCATIONIQ_LOOKUP_BATCH_SIZE = 50  # LocationIQ's max osm_ids per /lookup call
LOCATIONIQ_RESULTS_PER_QUERY = 20  # LocationIQ's max `limit` per search request
LOCATIONIQ_MIN_SECONDS_BETWEEN_CALLS = 1.0  # stay under the free-tier rate limit
LOCATIONIQ_MAX_RETRIES = 3  # attempts for transient failures (timeouts, 429, 5xx)
LOCATIONIQ_RETRY_BACKOFF_SECONDS = 2.0  # doubles each retry: 2s, 4s, ...
