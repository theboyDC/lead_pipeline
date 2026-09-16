from unittest.mock import MagicMock, patch

import pytest
import requests

from src import config
from src.extract_places import (
    PlacesAPIError,
    lookup_extratags,
    normalize_place,
    osm_ref,
    search_places,
)


def test_normalize_place_maps_locationiq_fields():
    raw = {
        "place_id": "281847169325",
        "osm_type": "way",
        "osm_id": "223225532",
        "lat": "-26.1076",
        "lon": "28.0567",
        "display_name": "Acme Tech, 1 Rivonia Rd, Sandton, Johannesburg, Gauteng, 2196, South Africa",
        "class": "office",
        "type": "it",
        "address": {"office": "Acme Tech", "suburb": "Sandton"},
        "namedetails": {"name": "Acme Tech"},
        "extratags": {
            "phone": "+27 11 555 0100",
            "website": "https://acmetech.co.za",
            "email": "hello@acmetech.co.za",
        },
    }

    result = normalize_place(raw)

    assert result["name"] == "Acme Tech"
    assert result["formatted_address"].startswith("Acme Tech,")
    assert result["formatted_phone_number"] == "+27 11 555 0100"
    assert result["website"] == "https://acmetech.co.za"
    assert result["email"] == "hello@acmetech.co.za"
    assert result["geometry"]["location"] == {"lat": -26.1076, "lng": 28.0567}
    assert result["types"] == ["office", "it"]
    assert result["url"] == "https://www.openstreetmap.org/way/223225532"


def test_normalize_place_prefers_separate_details_over_inline_extratags():
    place = {
        "place_id": "1",
        "osm_type": "way",
        "osm_id": "614957091",
        "lat": "-26.1",
        "lon": "28.0",
        "display_name": "Acme Tech, Johannesburg",
        "type": "office",
        "extratags": {"website": "https://stale.example"},  # from a bare /search call
    }
    details = {
        "namedetails": {"name": "Acme Tech"},
        "extratags": {"website": "https://acmetech.co.za", "email": "hello@acmetech.co.za"},
    }

    result = normalize_place(place, details)

    assert result["name"] == "Acme Tech"
    assert result["website"] == "https://acmetech.co.za"
    assert result["email"] == "hello@acmetech.co.za"


def test_normalize_place_handles_missing_extratags():
    raw = {
        "place_id": "1",
        "lat": "-26.2",
        "lon": "28.0",
        "display_name": "Some Startup, Braamfontein, Johannesburg",
        "type": "office",
    }

    result = normalize_place(raw)

    assert result["name"] == "Some Startup"
    assert result["formatted_phone_number"] is None
    assert result["website"] is None
    assert result["email"] is None
    assert result["url"] is None


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or []
    if status_code >= 400 and status_code != 404:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    else:
        resp.raise_for_status.side_effect = None
    return resp


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_search_places_raises_without_api_key(mock_get, mock_sleep, monkeypatch):
    monkeypatch.setattr(config, "LOCATIONIQ_API_KEY", "")

    with pytest.raises(PlacesAPIError, match="LOCATIONIQ_API_KEY"):
        search_places("tech startup in Johannesburg")

    mock_get.assert_not_called()


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_search_places_returns_empty_list_after_retrying_persistent_404(
    mock_get, mock_sleep, monkeypatch
):
    monkeypatch.setattr(config, "LOCATIONIQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "LOCATIONIQ_MAX_RETRIES", 2)
    mock_get.return_value = _mock_response(status_code=404)

    assert search_places("no results query") == []
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_search_places_retries_transient_404_then_succeeds(mock_get, mock_sleep, monkeypatch):
    monkeypatch.setattr(config, "LOCATIONIQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "LOCATIONIQ_MAX_RETRIES", 3)
    success = _mock_response(status_code=200, json_data=[{"place_id": "1"}])
    mock_get.side_effect = [_mock_response(status_code=404), success]

    results = search_places("tech startup in Johannesburg")

    assert results == [{"place_id": "1"}]
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_search_places_retries_transient_error_then_succeeds(mock_get, mock_sleep, monkeypatch):
    monkeypatch.setattr(config, "LOCATIONIQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "LOCATIONIQ_MAX_RETRIES", 3)
    success = _mock_response(status_code=200, json_data=[{"place_id": "1"}])
    mock_get.side_effect = [requests.ConnectionError("boom"), success]

    results = search_places("tech startup in Johannesburg")

    assert results == [{"place_id": "1"}]
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_search_places_gives_up_after_max_retries(mock_get, mock_sleep, monkeypatch):
    monkeypatch.setattr(config, "LOCATIONIQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "LOCATIONIQ_MAX_RETRIES", 2)
    mock_get.side_effect = requests.Timeout("timed out")

    with pytest.raises(PlacesAPIError):
        search_places("tech startup in Johannesburg")

    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_search_places_does_not_retry_non_retryable_http_error(mock_get, mock_sleep, monkeypatch):
    monkeypatch.setattr(config, "LOCATIONIQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "LOCATIONIQ_MAX_RETRIES", 3)
    mock_get.return_value = _mock_response(status_code=400)

    with pytest.raises(PlacesAPIError):
        search_places("bad query")

    mock_get.assert_called_once()
    mock_sleep.assert_not_called()


def test_osm_ref_formats_type_and_id():
    assert osm_ref({"osm_type": "way", "osm_id": "614957091"}) == "W614957091"
    assert osm_ref({"osm_type": "node", "osm_id": "1"}) == "N1"
    assert osm_ref({"osm_type": None, "osm_id": "1"}) is None
    assert osm_ref({}) is None


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_lookup_extratags_skips_request_when_no_places_have_osm_refs(mock_get, mock_sleep):
    assert lookup_extratags([{"place_id": "1"}]) == {}
    mock_get.assert_not_called()


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_lookup_extratags_batches_and_keys_by_osm_ref(mock_get, mock_sleep, monkeypatch):
    monkeypatch.setattr(config, "LOCATIONIQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "LOCATIONIQ_LOOKUP_BATCH_SIZE", 1)
    places = [
        {"osm_type": "way", "osm_id": "1"},
        {"osm_type": "node", "osm_id": "2"},
    ]
    mock_get.side_effect = [
        _mock_response(json_data=[{"osm_type": "way", "osm_id": "1", "extratags": {"website": "a.com"}}]),
        _mock_response(json_data=[{"osm_type": "node", "osm_id": "2", "extratags": {"website": "b.com"}}]),
    ]

    result = lookup_extratags(places)

    assert mock_get.call_count == 2
    assert result["W1"]["extratags"]["website"] == "a.com"
    assert result["N2"]["extratags"]["website"] == "b.com"


@patch("src.extract_places.time.sleep")
@patch("src.extract_places.requests.get")
def test_lookup_extratags_raises_without_api_key_when_there_is_something_to_look_up(
    mock_get, mock_sleep, monkeypatch
):
    monkeypatch.setattr(config, "LOCATIONIQ_API_KEY", "")

    with pytest.raises(PlacesAPIError, match="LOCATIONIQ_API_KEY"):
        lookup_extratags([{"osm_type": "way", "osm_id": "1"}])

    mock_get.assert_not_called()
