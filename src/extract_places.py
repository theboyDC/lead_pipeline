"""Discover candidate tech startups via the LocationIQ Search API (OpenStreetMap
data). Free tier: no credit card required, 5,000 requests/day.
https://locationiq.com/
"""
import logging
import time

import requests

from src import config

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class PlacesAPIError(Exception):
    pass


def _is_retryable(exc: requests.RequestException) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return False


def _get_with_retries(params: dict) -> requests.Response:
    for attempt in range(1, config.LOCATIONIQ_MAX_RETRIES + 1):
        try:
            resp = requests.get(
                config.LOCATIONIQ_SEARCH_URL, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS
            )
            if resp.status_code == 404:
                # LocationIQ returns 404 with an error body when there are zero results.
                return resp
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt >= config.LOCATIONIQ_MAX_RETRIES or not _is_retryable(exc):
                raise PlacesAPIError(f"LocationIQ request failed: {exc}") from exc
            wait = config.LOCATIONIQ_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "attempt %d/%d failed (%s), retrying in %.1fs",
                attempt,
                config.LOCATIONIQ_MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
    raise AssertionError("unreachable")  # loop always returns or raises


def search_places(query: str) -> list[dict]:
    """Run a LocationIQ Search query, bounded to the Johannesburg area.

    Unlike Google Places, LocationIQ's search response already includes
    address/coords and (when tagged in OpenStreetMap) contact extratags, so
    no separate "details" call is needed. Transient failures (timeouts, 429,
    5xx) are retried with exponential backoff before giving up.
    """
    if not config.LOCATIONIQ_API_KEY:
        raise PlacesAPIError("LOCATIONIQ_API_KEY is not set (see .env.example)")

    params = {
        "key": config.LOCATIONIQ_API_KEY,
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
        "limit": config.LOCATIONIQ_RESULTS_PER_QUERY,
        "viewbox": config.JOHANNESBURG_VIEWBOX,
        "bounded": 1,
        "countrycodes": "za",
    }

    resp = _get_with_retries(params)
    if resp.status_code == 404:
        logger.info("query=%r returned 0 places", query)
        return []
    results = resp.json()

    logger.info("query=%r returned %d places", query, len(results))
    return results


def normalize_place(place: dict) -> dict:
    """Map a raw LocationIQ result into the shape transform.build_record expects."""
    address = place.get("address") or {}
    namedetails = place.get("namedetails") or {}
    extratags = place.get("extratags") or {}
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
