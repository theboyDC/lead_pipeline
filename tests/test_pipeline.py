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
