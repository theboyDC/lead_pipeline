from src.transform import build_record, clean_text, normalize_phone


def test_clean_text_collapses_whitespace():
    assert clean_text("  Hello\n\nworld  ") == "Hello world"


def test_clean_text_none_and_empty():
    assert clean_text(None) is None
    assert clean_text("   ") is None


def test_normalize_phone_local_format():
    assert normalize_phone("011 123 4567") == "+27111234567"


def test_normalize_phone_already_international():
    assert normalize_phone("+27 11 123 4567") == "+27111234567"


def test_normalize_phone_none():
    assert normalize_phone(None) is None


def test_build_record_combines_places_and_enrichment():
    place_details = {
        "name": "  Acme Tech  ",
        "formatted_address": "1 Rivonia Rd, Sandton, Johannesburg",
        "international_phone_number": "+27 11 555 0100",
        "geometry": {"location": {"lat": -26.107, "lng": 28.056}},
        "website": "https://acmetech.co.za",
        "types": ["office", "it"],
        "url": "https://www.openstreetmap.org/way/223225532",
    }
    enrichment = {"description": "We build fintech APIs for African banks.", "email": "hello@acmetech.co.za"}

    record = build_record(place_details, enrichment, place_id="abc123", search_query="fintech company in Johannesburg")

    assert record["place_id"] == "abc123"
    assert record["name"] == "Acme Tech"
    assert record["address"] == "1 Rivonia Rd, Sandton, Johannesburg"
    assert record["contact"]["phone"] == "+27115550100"
    assert record["contact"]["website"] == "https://acmetech.co.za"
    assert record["contact"]["email"] == "hello@acmetech.co.za"
    assert record["description"] == "We build fintech APIs for African banks."
    assert record["location"] == {"lat": -26.107, "lng": 28.056}
    assert record["source_query"] == "fintech company in Johannesburg"
    assert record["map_url"] == "https://www.openstreetmap.org/way/223225532"
    assert "scraped_at" in record


def test_build_record_handles_missing_fields():
    record = build_record({}, {}, place_id="xyz", search_query="tech startup in Johannesburg")

    assert record["name"] is None
    assert record["contact"]["phone"] is None
    assert record["contact"]["email"] is None
    assert record["location"] == {"lat": None, "lng": None}
