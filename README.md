# nohayonline-scraper

Scrapy project that crawls nohayonline.com to extract kalaam metadata and lyrics, and stores results in PostgreSQL (with JSON export support for ad‑hoc runs).

The main spider `kalaam` walks the Masaib index, visits each kalaam detail page, and yields a normalized item with IDs, titles, reciters, poets, masaib category, bilingual lyrics, YouTube link, and source URL. A PostgreSQL pipeline upserts into a single table `kalaam` and bootstraps schema and indexes on first run.

See docs for details: `docs/architecture.md`, `docs/usage.md`, `docs/configuration.md`, `docs/database.md`, and `docs/development.md`.

## Quickstart

- Requirements: Python `>=3.10`, PostgreSQL 13+ (with `pg_trgm` extension), network access to `nohayonline.com`.
- Setup:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
  - Copy `.env.example` to `.env` and set your DB connection (or set env vars directly).

### Run and export to JSON (no DB)

If you only want a local JSON file and to skip the DB pipeline:

```
scrapy crawl kalaam -s ITEM_PIPELINES={} -O sample.json
```

The built‑in HTTP cache is enabled; subsequent runs will be faster and gentler on the site.

### Run with PostgreSQL

Provide DB credentials via environment or Scrapy settings. Easiest is a DSN/URI in `.env`:

```
POSTGRES_DSN=postgresql://postgres:mysecretpassword@127.0.0.1:5432/postgres
```

Then run:

```
scrapy crawl kalaam
```

On first run the pipeline will create table `kalaam`, required indexes, and enable `pg_trgm` if available. Items are upserted by `id` and deduplicated by `source_url`.

## Project Layout

- `nohayonline_scraper/spiders/kalaam.py`: Spider that extracts and normalizes kalaam records.
- `nohayonline_scraper/items.py`: Item schema used by the spider.
- `nohayonline_scraper/pipelines.py`: PostgreSQL upsert pipeline and schema bootstrap.
- `nohayonline_scraper/settings.py`: Scrapy settings; HTTP cache enabled by default.
- `docs/`: Additional documentation (architecture, usage, configuration, database, development).

## Notes

- Respect the website: robots.txt is obeyed and concurrency is conservative per domain.
- Incremental strategies are outlined in `docs/incremental_plan.md` and can be implemented iteratively.
- License: see `LICENSE`.
