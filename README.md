# Johannesburg Tech Startup Lead Pipeline

Finds tech startups and tech companies operating around Johannesburg and
stores them as unstructured documents in MongoDB, with:

- **name**
- **address** (plus lat/lng)
- **contact details** (phone, website, email where found)
- **what it does** (a short description scraped from the company's own site)

## How it works

```
 ┌────────────────────┐   ┌────────────────────┐   ┌──────────────┐
 │ LocationIQ Search    │──▶│ Website scrape       │──▶│ transform.py   │
 │ (extract_places.py)  │   │ (enrich.py)          │   │ build_record   │
 └────────────────────┘   └────────────────────┘   └──────┬───────┘
                                                              │
                                                              ▼
                                                    ┌────────────────┐
                                                    │ MongoDB          │
                                                    │ startups coll.   │
                                                    │ (load.py upsert) │
                                                    └────────────────┘
```

1. **Discover** — `extract_places.py` runs LocationIQ Search queries bounded
   to a box around Johannesburg. `config.SEARCH_QUERIES` is the cross product
   of `STARTUP_QUERY_TERMS` (tech startup, fintech company/startup, software
   company, IT company, startup incubator/accelerator, coworking space, AI
   startup, SaaS company, ...) and `JOHANNESBURG_AREAS` (Johannesburg,
   Sandton, Rosebank, Braamfontein, Melrose Arch, Randburg, Fourways,
   Midrand, Bryanston) — 108 queries by default. Add a term or area to
   either list to widen coverage without touching the pipeline. LocationIQ is
   built on OpenStreetMap data and its search response already includes
   address, coordinates, and — when tagged in OSM — phone/website/email, so
   no separate "details" call is needed (`normalize_place` maps the raw
   result into a consistent shape). `is_business_place` then drops results
   that aren't tagged as an actual office/company (e.g. a street, station, or
   landmark whose name happens to contain "Johannesburg") before the
   extratags lookup and website scrape run on them.
2. **Enrich** — `enrich.py` visits the company's own website (if listed),
   respecting `robots.txt`, and pulls a description (meta description /
   `og:description`, falling back to the first substantial paragraph) plus
   an email address if one is published.
3. **Transform** — `transform.py` cleans whitespace, normalizes phone numbers
   to `+27...` format, computes a `lead_score` (0-4, one point each for
   phone/website/email/description present), and assembles one document per
   company. Pure functions, fully unit tested without any network calls.
4. **Dedup** — `pipeline.py` tracks the website domain of every company
   processed in the run; if a later place resolves to a domain already
   captured (e.g. the same company surfaced by two different search queries,
   or listed twice in OSM under different `place_id`s), it's skipped before
   the enrichment scrape runs.
5. **Load** — `load.py` upserts each document into MongoDB keyed by
   LocationIQ's `place_id`, so re-running the pipeline updates existing leads
   instead of duplicating them.

`pipeline.py` orchestrates all of the above and logs progress/counts to
`logs/pipeline.log`.

## Document shape (MongoDB `startups` collection)

```json
{
  "place_id": "281847169325",
  "name": "Acme Tech",
  "address": "Acme Tech, 1 Rivonia Rd, Sandton, Johannesburg, Gauteng, 2196, South Africa",
  "location": { "lat": -26.107, "lng": 28.056 },
  "contact": {
    "phone": "+27115550100",
    "website": "https://acmetech.co.za",
    "email": "hello@acmetech.co.za"
  },
  "description": "We build fintech APIs for African banks.",
  "types": ["office", "it"],
  "map_url": "https://www.openstreetmap.org/way/223225532",
  "source_query": "fintech company in Johannesburg",
  "scraped_at": "2026-09-14T12:00:00+00:00",
  "lead_score": 4
}
```

It's intentionally schema-flexible — new fields can be added to a record
(e.g. `funding_stage`, `linkedin`) without a migration.

## Setup

1. **Get a free LocationIQ API key** — sign up at
   [locationiq.com](https://locationiq.com), no credit card required (free
   tier: 5,000 requests/day). Copy `.env.example` to `.env` and fill it in:

   ```bash
   cp .env.example .env
   # edit .env: LOCATIONIQ_API_KEY=...
   ```

2. **Start MongoDB** (and mongo-express, a web UI at http://localhost:8081
   for browsing the data):

   ```bash
   docker compose up -d
   ```

3. **Install dependencies**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run the pipeline**:

   ```bash
   python -m src.pipeline --limit 20   # cap results while testing
   python -m src.pipeline              # full run across all queries
   ```

## Exporting leads

Once leads are in MongoDB, export them to a flat CSV for outreach or CRM import:

```bash
python -m src.export --out leads.csv
```

Each row is one company with the nested `location`/`contact` fields flattened
(`lat`, `lng`, `phone`, `website`, `email`, ...). `leads.csv` is gitignored
since it contains scraped contact details.

## Dashboard

A Streamlit dashboard reads directly from the MongoDB `startups` collection —
KPIs (total leads, % with phone/website/email), leads by source query, lead
score distribution, a map of locations, and a filterable/sortable table.

```bash
streamlit run src/dashboard.py
```

Opens at http://localhost:8501. Filter by minimum lead score, source query,
or name in the sidebar. Data is cached for 60s, so re-run the pipeline and
refresh the page to see new leads.

## Testing

```bash
pytest
```

Tests cover `transform.py`, `enrich.py`, and `extract_places.py`'s parsing
logic with fixture HTML/data — no network or API key required to run them.

## Compliance notes

- **LocationIQ / OpenStreetMap data is ODbL-licensed** — if you publish or
  redistribute this data (rather than using it for personal lead-gen), you
  must attribute "© OpenStreetMap contributors" and share alike under the
  same license. See [locationiq.com/terms](https://locationiq.com/terms) and
  [OpenStreetMap's copyright page](https://www.openstreetmap.org/copyright).
- Coverage depends on OSM's community tagging, so this will surface fewer
  results than Google Places for the same queries, and some entries will be
  missing phone/website even where the business exists.
- **Website scraping** respects `robots.txt` and uses a descriptive
  `User-Agent`, but you should still keep request volume low and review each
  target site's terms if scraping beyond a handful of companies.
- Store `.env` (with your API key) outside of version control — it's already
  in `.gitignore`.

## Project structure

```
lead_pipeline/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml
├── src/
│   ├── config.py
│   ├── db.py
│   ├── extract_places.py
│   ├── enrich.py
│   ├── transform.py
│   ├── load.py
│   ├── export.py
│   ├── dashboard.py
│   └── pipeline.py
├── logs/
│   └── .gitkeep
└── tests/
    ├── test_transform.py
    ├── test_enrich.py
    └── test_extract_places.py
```
