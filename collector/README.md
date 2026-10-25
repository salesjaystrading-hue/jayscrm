# JAYS tender collector (Phase 2)

Flow: GitHub Actions -> pinned Tender_Scraper (GeM, CPPP only) -> `normalise.py` (validate/clean) -> `relevance.py` (JAYS keywords, `jays_keywords.json`) -> `ingest.py` -> `tender_ingest_batch()` in Supabase -> Tender Centre.

* Dry-run is the default and writes nothing. Real writes need the repo variable `ENABLE_PRODUCTION_WRITES=true` AND mode `ingest`.
* Secrets (names only): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` - GitHub Actions secrets. Never put them in index.html or any file.
* Kerala e-Tender and all CAPTCHA portals are not collected (manual import only).
* Edit `jays_keywords.json` to change what matches; no code change needed. Run tests: `python -m unittest discover -s collector/tests`.
* Rollback: `supabase/migrations/20261025_008_ROLLBACK.sql`; delete `.github/workflows/tender-collect.yml` to stop collection.
* Note: GitHub Pages publishes this whole repo, so files here are publicly readable. No secrets are stored here.
