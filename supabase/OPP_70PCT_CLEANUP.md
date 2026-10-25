# Project Opportunity: remove completed projects (expenditure >= 70%)

Rule: Expenditure completed % = Expenditure / FundTotal x 100 (the source sheets have no percentage column; an explicit "Expenditure Completed %" column wins if a file has one). >= 70% (exactly 70 included) is excluded. Blank / non-numeric / FundTotal<=0 is kept for review, never deleted or skipped.

Database (already applied to project ufpaxvflwaqesdueqiob): migration `20261025_009_opp_completed_projects_rule.sql` (+ `opp_cleanup_page` fix). Rollback: `20261025_009_ROLLBACK.sql`.
* `opp_merge_batch` (used by every import path) skips >=70% rows server-side and returns skippedCompleted / reviewCount.
* `opp_cleanup_preview / opp_cleanup_page / opp_cleanup_delete`: admin-only, SECURITY DEFINER, no service key, expected-count guard, audit rows in `opp_cleanup_log`. Projects saved in My Opportunities are protected.

Use (Admin): Project Opportunities -> Delete Data tab -> "Remove completed projects": 1 Preview, 2 Download backup file, 3 Delete (type DELETE). Safe to re-run.
Restore: the backup file is a JSON list of {key, data}; rows can be re-inserted into opp_projects_rows.
Disk space is only returned after the table is rewritten (VACUUM FULL opp_projects_rows), which needs a short lock.
