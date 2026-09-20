from unittest.mock import MagicMock, patch

from src.pipeline import run


def _place(place_id, website, name="Acme"):
    return {
        "place_id": place_id,
        "name": name,
        "extratags": {"website": website} if website else {},
        "lat": "-26.1",
        "lon": "28.0",
        "display_name": f"{name}, Johannesburg",
        "class": "office",
        "type": "office",
    }


@patch("src.pipeline.time.sleep")
@patch("src.pipeline.get_collection")
@patch("src.pipeline.enrich.enrich_from_website")
@patch("src.pipeline.extract_places.search_places")
def test_run_skips_duplicate_domain_across_queries(mock_search, mock_enrich, mock_get_collection, mock_sleep):
    mock_get_collection.return_value = MagicMock()
    mock_enrich.return_value = {"description": None, "email": None}
    mock_search.side_effect = [
        [_place("1", "https://acmetech.co.za")],
        [_place("2", "https://www.acmetech.co.za/contact")],  # same company, different place_id
    ]

    stats = run(["query one", "query two"], limit=None)

    assert stats["discovered"] == 2
    assert stats["processed"] == 1
    assert stats["skipped_duplicate_domain"] == 1
    assert mock_enrich.call_count == 1


@patch("src.pipeline.time.sleep")
@patch("src.pipeline.get_collection")
@patch("src.pipeline.enrich.enrich_from_website")
@patch("src.pipeline.extract_places.search_places")
def test_run_processes_places_without_websites(mock_search, mock_enrich, mock_get_collection, mock_sleep):
    mock_get_collection.return_value = MagicMock()
    mock_search.side_effect = [[_place("1", None), _place("2", None)]]

    stats = run(["query one"], limit=None)

    assert stats["processed"] == 2
    assert stats["skipped_duplicate_domain"] == 0
    mock_enrich.assert_not_called()


@patch("src.pipeline.time.sleep")
@patch("src.pipeline.get_collection")
@patch("src.pipeline.enrich.enrich_from_website")
@patch("src.pipeline.extract_places.lookup_extratags")
@patch("src.pipeline.extract_places.search_places")
def test_run_uses_lookup_extratags_for_contact_details(
    mock_search, mock_lookup, mock_enrich, mock_get_collection, mock_sleep
):
    mock_get_collection.return_value = MagicMock()
    mock_enrich.return_value = {"description": None, "email": None}
    place = {
        "place_id": "1",
        "osm_type": "way",
        "osm_id": "999",
        "lat": "-26.1",
        "lon": "28.0",
        "display_name": "Acme Tech, Johannesburg",
        "class": "office",
        "type": "office",
        # bare /search result: no extratags inline
    }
    mock_search.side_effect = [[place]]
    mock_lookup.return_value = {"W999": {"extratags": {"website": "https://acmetech.co.za"}}}

    stats = run(["query one"], limit=None)

    assert stats["processed"] == 1
    mock_lookup.assert_called_once_with([place])
    mock_enrich.assert_called_once_with("https://acmetech.co.za")


@patch("src.pipeline.time.sleep")
@patch("src.pipeline.get_collection")
@patch("src.pipeline.enrich.enrich_from_website")
@patch("src.pipeline.extract_places.lookup_extratags")
@patch("src.pipeline.extract_places.search_places")
def test_run_filters_out_non_business_places(
    mock_search, mock_lookup, mock_enrich, mock_get_collection, mock_sleep
):
    mock_get_collection.return_value = MagicMock()
    road = {
        "place_id": "1",
        "lat": "-26.1",
        "lon": "28.0",
        "display_name": "Johannesburg Road, Johannesburg",
        "class": "highway",
        "type": "primary",
    }
    office = _place("2", "https://acmetech.co.za")
    mock_search.side_effect = [[road, office]]
    mock_lookup.return_value = {}
    mock_enrich.return_value = {"description": None, "email": None}

    stats = run(["query one"], limit=None)

    assert stats["discovered"] == 1
    assert stats["processed"] == 1
    assert stats["skipped_non_business"] == 1
    mock_lookup.assert_called_once_with([road, office])


@patch("src.pipeline.time.sleep")
@patch("src.pipeline.get_collection")
@patch("src.pipeline.enrich.enrich_from_website")
@patch("src.pipeline.extract_places.lookup_extratags")
@patch("src.pipeline.extract_places.search_places")
def test_run_filters_on_class_from_lookup_when_search_omits_it(
    mock_search, mock_lookup, mock_enrich, mock_get_collection, mock_sleep
):
    """LocationIQ /search returns no class/type; /lookup does."""
    mock_get_collection.return_value = MagicMock()
    mock_enrich.return_value = {"description": None, "email": None}

    def bare(place_id, osm_id):
        return {
            "place_id": place_id,
            "osm_type": "node",
            "osm_id": osm_id,
            "lat": "-26.1",
            "lon": "28.0",
            "display_name": f"Place {place_id}, Sandton",
        }

    company, college = bare("1", "100"), bare("2", "200")
    mock_search.side_effect = [[company, college]]
    mock_lookup.return_value = {
        "N100": {"class": "office", "type": "it", "extratags": {}},
        "N200": {"class": "amenity", "type": "college", "extratags": {}},
    }

    stats = run(["query one"], limit=None)

    assert stats["processed"] == 1
    assert stats["skipped_non_business"] == 1
