"""Send normalised rows to Supabase through tender_ingest_batch(). Secrets come from the environment only
and are never printed. Dry-run is the default and writes nothing."""
import csv, glob, json, os, sys, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relevance import Relevance
from normalise import to_row

BATCH = 500


def read_csvs(folder):
    out = []
    for p in sorted(glob.glob(os.path.join(folder, "*.csv"))):
        if os.path.basename(p).startswith("errors"):
            continue
        with open(p, encoding="utf-8-sig", newline="") as fh:
            out.extend(csv.DictReader(fh))
    return out


def rpc(url, key, portal, rows, trigger, dry):
    body = json.dumps({"p_portal": portal, "p_rows": rows, "p_trigger": trigger, "p_file_name": "github-actions", "p_dry_run": dry}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/rest/v1/rpc/tender_ingest_batch", data=body, method="POST",
                                 headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError("ingest HTTP %s: %s" % (e.code, e.read().decode()[:300]))  # body only, never headers


def main(folder, mode="dry-run", trigger="manual", report="collector_report.json"):
    dry = mode != "ingest"
    rel = Relevance()
    recs = read_csvs(folder)
    by_portal, skipped = {}, {}
    for rec in recs:
        row, why, _ = to_row(rec, rel)
        if row is None:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        by_portal.setdefault(row.pop("portal"), []).append(row)
    summary = {"mode": mode, "scraped": len(recs), "skipped": skipped, "portals": {}}
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    for portal, rows in by_portal.items():
        # the DB rejects rows with INVALID: dates and records the reason; strip the marker value to null-safe string
        agg = {"sent": len(rows), "inserted": 0, "updated": 0, "duplicates_skipped": 0, "rejected": 0, "errors": []}
        if not (url and key):
            agg["note"] = "no database credentials in environment - local validation only"
            summary["portals"][portal] = agg
            continue
        for i in range(0, len(rows), BATCH):
            res = rpc(url, key, portal, rows[i:i + BATCH], trigger if trigger in ("manual", "scheduled") else "manual", dry)
            for k in ("inserted", "updated", "duplicates_skipped", "rejected"):
                agg[k] += res.get(k, 0)
            agg["errors"].extend(res.get("errors", [])[:20])
        summary["portals"][portal] = agg
    with open(report, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps({k: v for k, v in summary.items()}, indent=2)[:4000])
    return summary


if __name__ == "__main__":
    import argparse
    a = argparse.ArgumentParser()
    a.add_argument("folder"); a.add_argument("--mode", choices=["dry-run", "ingest"], default="dry-run")
    a.add_argument("--trigger", default="manual"); a.add_argument("--report", default="collector_report.json")
    x = a.parse_args(); main(x.folder, x.mode, x.trigger, x.report)
