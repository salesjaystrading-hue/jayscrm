"""JAYS keyword relevance. Pure functions, no network, no secrets.
Exact vs broad matches with stored reasons; generic words alone never match."""
import json, re, os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config(path=None):
    with open(path or os.path.join(HERE, "jays_keywords.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _rx(term):
    parts = [p for p in re.split(r"[\s\-]+", term.strip()) if p]
    body = r"[\s\-]+".join(re.escape(p) for p in parts)
    return re.compile(r"(?<![A-Za-z0-9])" + body + r"s?(?![A-Za-z0-9])", re.I)


class Relevance:
    def __init__(self, cfg=None):
        self.cfg = cfg or load_config()
        self.generic = {g.lower() for g in self.cfg.get("generic_words", [])}
        self.groups = [(g, [(t, _rx(t)) for t in g.get("exact", [])], [(t, _rx(t)) for t in g.get("broad", [])]) for g in self.cfg["groups"]]
        self.buyers = [(t, _rx(t)) for t in self.cfg.get("buyer_types", [])]
        self.excluded = [(t, _rx(t)) for t in self.cfg.get("excluded", [])]
        self.min_broad = int(self.cfg.get("min_broad_hits", 2))
        self.threshold = int(self.cfg.get("relevant_if_score_at_least", 30))

    def search_terms(self):
        """Specific phrases (exact terms) used to drive portal searches."""
        return sorted({t for g in self.cfg["groups"] for t in g.get("exact", [])})

    def score(self, *texts):
        hay = " ".join(t for t in texts if t)
        if not hay.strip():
            return {"relevant": False, "score": 0, "reasons": [], "match_type": "none"}
        for t, rx in self.excluded:
            if rx.search(hay):
                return {"relevant": False, "score": 0, "reasons": [{"word": t, "weight": 0, "tier": "Excluded keyword"}], "match_type": "excluded"}
        reasons, total, exact_hit = [], 0, False
        broad_words = set()
        for g, exacts, broads in self.groups:
            for t, rx in exacts:
                if t.lower() in self.generic:
                    continue
                if rx.search(hay):
                    exact_hit = True
                    w = int(g.get("weight", 30))
                    reasons.append({"word": t, "weight": w, "tier": g["label"] + " (exact)"})
                    total += w
            for t, rx in broads:
                if t.lower() in self.generic:
                    continue
                if rx.search(hay):
                    broad_words.add(t.lower())
                    reasons.append({"word": t, "weight": 15, "tier": g["label"] + " (broad)"})
        buyer = [t for t, rx in self.buyers if rx.search(hay)]
        for t in buyer:
            reasons.append({"word": t, "weight": 15, "tier": "Buyer type"})
        broad_ok = len(broad_words) >= self.min_broad or (len(broad_words) >= 1 and buyer)
        if exact_hit:
            mtype = "exact"
        elif broad_ok:
            mtype = "broad"
            total += 15 * len(broad_words)
        else:
            mtype = "none"
        if buyer and mtype != "none":
            total += 15
        seen, uniq = set(), []
        for r in reasons:
            k = (r["word"].lower(), r["tier"])
            if k not in seen:
                seen.add(k); uniq.append(r)
        if mtype == "none":
            # keep reasons so a rejection can be explained, but not relevant
            return {"relevant": False, "score": 0, "reasons": uniq[:12], "match_type": "none"}
        score = min(100, total)
        return {"relevant": score >= self.threshold, "score": score, "reasons": uniq[:12], "match_type": mtype}
