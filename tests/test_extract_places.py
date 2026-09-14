from src.extract_places import normalize_place


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
