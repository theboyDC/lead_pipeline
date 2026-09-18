"""Discover candidate tech startups via the LocationIQ Search API (OpenStreetMap
data). Free tier: no credit card required, 5,000 requests/day.
https://locationiq.com/
"""
import logging
import re
import time

import requests

from src import config

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class PlacesAPIError(Exception):
    pass


class PlacesAuthError(PlacesAPIError):
    """The API key was rejected (401/403); retrying or continuing is pointless."""


_KEY_PARAM_RE = re.compile(r"(key=)[^&\s]+")


def _redact(text: str) -> str:
    return _KEY_PARAM_RE.sub(r"\1***", text)


def _is_retryable(exc: requests.RequestException) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return False


def _get_with_retries(url: str, params: dict) -> requests.Response:
    for attempt in range(1, config.LOCATIONIQ_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 404:
                # LocationIQ returns 404 for genuine zero-result queries, but
                # also (empirically, reliably) for transient hiccups. Treat it
                # like any other transient failure and only accept it as a
                # real empty result once retries are exhausted.
                if attempt >= config.LOCATIONIQ_MAX_RETRIES:
                    return resp
                wait = config.LOCATIONIQ_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "attempt %d/%d got 404 'Unable to geocode', retrying in %.1fs",
                    attempt,
                    config.LOCATIONIQ_MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
                continue
            if resp.status_code in (401, 403):
                raise PlacesAuthError(
                    f"LocationIQ rejected the API key (HTTP {resp.status_code}); "
                    "check LOCATIONIQ_API_KEY in .env"
                ) from None
            resp.raise_for_status()
            return resp
        except PlacesAuthError:
            raise
        except requests.RequestException as exc:
            if attempt >= config.LOCATIONIQ_MAX_RETRIES or not _is_retryable(exc):
                raise PlacesAPIError(f"LocationIQ request failed: {_redact(str(exc))}") from None
            wait = config.LOCATIONIQ_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "attempt %d/%d failed (%s), retrying in %.1fs",
                attempt,
                config.LOCATIONIQ_MAX_RETRIES,
                _redact(str(exc)),
                wait,
            )
            time.sleep(wait)
    raise AssertionError("unreachable")  # loop always returns or raises


def search_places(query: str) -> list[dict]:
    """Run a LocationIQ Search query, bounded to the Johannesburg area.

    Deliberately does NOT request extratags/namedetails here: LocationIQ's
    /search endpoint reliably 404s ("Unable to geocode") when those params
    are combined with a free-text category query like "tech startup in
    Johannesburg" (it works fine for named-entity queries e.g. "Sandton
    City"). Contact details are fetched separately per result via
    lookup_extratags(), which uses the /lookup endpoint and doesn't hit this
    restriction. Transient failures (timeouts, 429, 5xx, and 404s that don't
    resolve on retry) are retried with exponential backoff before giving up.
    """
    if not config.LOCATIONIQ_API_KEY:
        raise PlacesAPIError("LOCATIONIQ_API_KEY is not set (see .env.example)")

    params = {
        "key": config.LOCATIONIQ_API_KEY,
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": config.LOCATIONIQ_RESULTS_PER_QUERY,
        "viewbox": config.JOHANNESBURG_VIEWBOX,
        "bounded": 1,
        "countrycodes": "za",
    }

    resp = _get_with_retries(config.LOCATIONIQ_SEARCH_URL, params)
    if resp.status_code == 404:
        logger.info("query=%r returned 0 places", query)
        return []
    results = resp.json()

    logger.info("query=%r returned %d places", query, len(results))
    return results


_BUSINESS_CLASSES = {"office"}
_BUSINESS_AMENITY_TYPES = {"coworking_space"}


def is_business_place(place: dict) -> bool:
    """Best-effort filter to drop non-business OSM results.

    Broad category queries (e.g. "tech company in Rosebank") frequently match
    a street, station, school, or landmark whose name happens to contain a
    place name rather than an actual company (e.g. "Johannesburg Road",
    "Johannesburg Correctional Centre"). Requires OSM tagging that indicates
    an office/company (`office=*`) or a coworking space
    (`amenity=coworking_space`); everything else is dropped before the
    (rate-limited) extratags lookup and website scrape run on it.
    """
    place_class = place.get("class")
    place_type = place.get("type")
    if place_class in _BUSINESS_CLASSES:
        return True
    return place_class == "amenity" and place_type in _BUSINESS_AMENITY_TYPES


def osm_ref(place: dict) -> str | None:
    """Build the "W123"/"N123"/"R123" id lookup(osm_ids=...) expects from a
    place's osm_type/osm_id, or None if the place doesn't carry them."""
    osm_type = place.get("osm_type")
    osm_id = place.get("osm_id")
    if not osm_type or not osm_id:
        return None
    return f"{osm_type[0].upper()}{osm_id}"


def lookup_extratags(places: list[dict]) -> dict[str, dict]:
    """Batch-fetch extratags/namedetails (phone/website/email/alt-names) for
    search results via LocationIQ's /lookup endpoint, keyed by osm_ref().

    See search_places() for why this is a separate call instead of just
    passing extratags=1/namedetails=1 to /search.
    """
    refs = [ref for ref in (osm_ref(p) for p in places) if ref]
    if not refs:
        return {}
    if not config.LOCATIONIQ_API_KEY:
        raise PlacesAPIError("LOCATIONIQ_API_KEY is not set (see .env.example)")

    details: dict[str, dict] = {}
    for i in range(0, len(refs), config.LOCATIONIQ_LOOKUP_BATCH_SIZE):
        batch = refs[i : i + config.LOCATIONIQ_LOOKUP_BATCH_SIZE]
        params = {
            "key": config.LOCATIONIQ_API_KEY,
            "osm_ids": ",".join(batch),
            "format": "json",
            "addressdetails": 1,
            "extratags": 1,
            "namedetails": 1,
        }
        resp = _get_with_retries(config.LOCATIONIQ_LOOKUP_URL, params)
        if resp.status_code == 404:
            continue
        for result in resp.json():
            ref = osm_ref(result)
            if ref:
                details[ref] = result
    return details


def normalize_place(place: dict, details: dict | None = None) -> dict:
    """Map a raw LocationIQ search result into the shape transform.build_record
    expects. `details` is the matching lookup_extratags() result for this
    place (carrying extratags/namedetails); falls back to `place` itself so
    callers that already have extratags inline (e.g. tests) keep working.
    """
    source = details if details is not None else place
    address = place.get("address") or {}
    namedetails = source.get("namedetails") or {}
    extratags = source.get("extratags") or {}
    place_type = place.get("type", "")

    name = (
        namedetails.get("name")
        or address.get(place_type)
        or (place.get("display_name") or "").split(",")[0]
        or None
    )
    phone = extratags.get("phone") or extratags.get("contact:phone")
    website = extratags.get("website") or extratags.get("contact:website")
    email = extratags.get("email") or extratags.get("contact:email")

    osm_type = place.get("osm_type")
    osm_id = place.get("osm_id")
    map_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type and osm_id else None

    return {
        "name": name,
        "formatted_address": place.get("display_name"),
        "formatted_phone_number": phone,
        "international_phone_number": phone,
        "website": website,
        "email": email,
        "geometry": {
            "location": {
                "lat": float(place["lat"]) if place.get("lat") is not None else None,
                "lng": float(place["lon"]) if place.get("lon") is not None else None,
            }
        },
        "types": [t for t in (place.get("class"), place_type) if t],
        "url": map_url,
    }
