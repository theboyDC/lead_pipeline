import csv

from src.export import export_to_csv, flatten_record


def _sample_record(**overrides):
    record = {
        "place_id": "123",
        "name": "Acme Tech",
        "address": "1 Rivonia Rd, Sandton",
        "location": {"lat": -26.107, "lng": 28.056},
        "contact": {"phone": "+27115550100", "website": "https://acmetech.co.za", "email": "hi@acmetech.co.za"},
        "description": "We build fintech APIs.",
        "types": ["office", "it"],
        "map_url": "https://www.openstreetmap.org/way/1",
        "source_query": "fintech company in Johannesburg",
        "scraped_at": "2026-09-14T12:00:00+00:00",
    }
    record.update(overrides)
    return record


def test_flatten_record_maps_nested_fields():
    row = flatten_record(_sample_record())

    assert row["name"] == "Acme Tech"
    assert row["lat"] == -26.107
    assert row["lng"] == 28.056
    assert row["phone"] == "+27115550100"
    assert row["website"] == "https://acmetech.co.za"
    assert row["email"] == "hi@acmetech.co.za"
    assert row["types"] == "office;it"
    assert row["place_id"] == "123"


def test_flatten_record_handles_missing_nested_fields():
    record = _sample_record(location={}, contact={}, types=[])
    row = flatten_record(record)

    assert row["lat"] is None
    assert row["phone"] is None
    assert row["types"] == ""


def test_export_to_csv_writes_header_and_rows(tmp_path):
    records = [_sample_record(), _sample_record(place_id="456", name="Beta Soft")]
    out_path = tmp_path / "leads.csv"

    count = export_to_csv(records, out_path)

    assert count == 2
    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["name"] == "Acme Tech"
    assert rows[1]["place_id"] == "456"


def test_export_to_csv_empty_records_writes_only_header(tmp_path):
    out_path = tmp_path / "leads.csv"

    count = export_to_csv([], out_path)

    assert count == 0
    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows == []
