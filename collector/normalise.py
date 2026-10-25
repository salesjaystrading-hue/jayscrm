"""Turn scraper CSV rows into rows for tender_ingest_batch(). Validates, never invents data."""
import re
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
SOURCE_TO_PORTAL = {"gem": "GEM", "cppp": "CPPP"}   # only portals audited as CAPTCHA-free
MAX_TITLE, MAX_TEXT, MAX_URL = 500, 4000, 2000


def _clip(v, n):
    v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v or "")).strip()
    return v[:n]


def parse_dt(v):
    v = (v or "").strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(v, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc) if fmt.endswith("Z") else d.replace(tzinfo=IST)
            return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return None


def safe_url(u):
    u = (u or "").strip()
    return u[:MAX_URL] if re.match(r"^https?://[^\s]+$", u, re.I) else None


def to_row(rec, rel):
    """Returns (row_or_None, skip_reason_or_None, relevance dict)."""
    portal = SOURCE_TO_PORTAL.get((rec.get("source") or "").strip().lower())
    if not portal:
        return None, "unsupported source: " + _clip(rec.get("source"), 40), None
    title = _clip(rec.get("title"), MAX_TITLE)
    if not title:
        return None, "missing title", None
    desc = _clip(rec.get("description"), MAX_TEXT)
    r = rel.score(title, desc, rec.get("organization"))
    if not r["relevant"]:
        return None, "not relevant (" + r["match_type"] + ")", r
    row = {
        "portal": portal,
        "title": title,
        "description": desc or None,
        "portal_tender_id": _clip(rec.get("tender_id"), 120) or None,
        "buyer_name": _clip(rec.get("organization"), 300) or None,
        "state": _clip(rec.get("state"), 80) or None,
        "published_at": parse_dt(rec.get("published_date")),
        "closing_at": parse_dt(rec.get("closing_date")),
        "bid_type": _clip(rec.get("tender_type"), 40) if rec.get("tender_type") != "Unidentified" else None,
        "source_url": safe_url(rec.get("source_url")),
        "match_score": r["score"],
        "match_reasons": r["reasons"],
    }
    # Dates present in the source but unparseable are dropped by the DB as a rejected row rather than guessed.
    if (rec.get("closing_date") or "").strip() and row["closing_at"] is None:
        row["closing_at"] = "INVALID:" + _clip(rec.get("closing_date"), 40)
    return {k: v for k, v in row.items() if v is not None}, None, r
