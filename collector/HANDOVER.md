# Tender collection - handover

> **Result of the first dry run (25 Oct 2026):** GitHub's servers could not reach GeM (connection refused) or CPPP (timeout), so 0 tenders were collected. The chosen working method is **Excel/CSV import in Tender Centre** (Import button). The GitHub collector below stays switched off (`ENABLE_SCHEDULE`/`ENABLE_PRODUCTION_WRITES` unset) unless it is moved to a machine in India.

## What is automated
| Portal | Status |
|---|---|
| GeM (open bids) | Automated by GitHub Actions - NOT yet proven from GitHub runners; run a dry run first |
| CPPP | Automated - same caveat; scans a capped number of pages |
| Kerala e-Tender, other CAPTCHA/GePNIC portals | Manual only (Excel/CSV import or manual entry). Never bypassed |

## One-time setup (beginner steps)
1. Merge the branches in order: tender-collector-phase2, tender-dashboard-phase3, tender-bid-phase4, tender-schedule-phase5.
2. GitHub repo > Settings > Secrets and variables > Actions > **Secrets**: add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (Supabase > Project Settings > API). Never paste the key anywhere else.
3. Actions tab > "Tender collection" > Run workflow > mode **dry-run**. Open the run summary / `collector-report` artifact. Check: rows scraped, rows sent, rejected, `silent_sources` is empty.
4. If the report looks right: Settings > Variables: `ENABLE_PRODUCTION_WRITES` = `true`, run once with mode **ingest**, then look at Tender Centre > Collection Runs.
5. Only then set variable `ENABLE_SCHEDULE` = `true` for the daily 06:00 IST run.

## Switch off / rollback
* Stop schedule: delete variable `ENABLE_SCHEDULE`. Stop writes: delete `ENABLE_PRODUCTION_WRITES`.
* Remove collector: delete `.github/workflows/tender-collect.yml`.
* Database: run `supabase/migrations/20261025_008_ROLLBACK.sql`.
* Collected tenders can be deleted by an admin in Tender Centre; notes, assignment and review status are never overwritten by the collector.

## Known limitations
* Not tested against live portals (sandbox could not reach them). Portal layouts can change and break scraping.
* Tender_Scraper has no licence; the workflow checks it out at a pinned commit and does not copy its code into this repo. Ask the author to add a licence.
* The service-role key is powerful; it lives only in GitHub secrets. Rotate it if exposed.
* Tender Centre cannot start a run itself (no GitHub token in the browser); it links to GitHub Actions.
* GitHub Pages publishes this repo's files, including collector/ and supabase/ (no secrets inside).
