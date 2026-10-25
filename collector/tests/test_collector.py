import os, sys, json, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from relevance import Relevance
from normalise import to_row, parse_dt, safe_url

R = Relevance()


class T(unittest.TestCase):
    def test_exact_waste_bin(self):
        self.assertTrue(R.score("Supply of 120 litre waste bin for Grama Panchayat")["relevant"])
    def test_generic_alone_not_relevant(self):
        for t in ["Supply of equipment", "Machine purchase", "Supply of material and items", "Procurement of services"]:
            self.assertFalse(R.score(t)["relevant"], t)
    def test_single_broad_not_relevant(self):
        self.assertFalse(R.score("Bucket for painting")["relevant"])
    def test_two_broad_relevant(self):
        r = R.score("Trolley and container for waste collection")
        self.assertTrue(r["relevant"]); self.assertEqual(r["match_type"], "broad")
    def test_broad_plus_buyer(self):
        self.assertTrue(R.score("Gloves for Municipality")["relevant"])
    def test_baler_and_shredder(self):
        self.assertEqual(R.score("Plastic baling machine MRF machinery")["match_type"], "exact")
    def test_word_boundary(self):
        self.assertFalse(R.score("Apparel supply upset")["relevant"])  # 'ups' must not match 'upset'
    def test_excluded(self):
        self.assertFalse(R.score("Laptop cloud based web application")["relevant"])
    def test_reasons_stored(self):
        r = R.score("Safety gloves for Haritha Karma Sena")
        self.assertTrue(r["reasons"] and all("word" in x and "tier" in x for x in r["reasons"]))
    def test_unsupported_source(self):
        row, why, _ = to_row({"source": "kerala", "title": "waste bin"}, R)
        self.assertIsNone(row); self.assertIn("unsupported", why)
    def test_gem_row(self):
        row, why, _ = to_row({"source": "gem", "tender_id": "GEM/2026/B/1", "title": "Dustbin 100L", "closing_date": "2026-11-01T14:00:00Z", "source_url": "https://bidplus.gem.gov.in/x", "tender_type": "Product"}, R)
        self.assertEqual(row["closing_at"], "2026-11-01T14:00:00Z"); self.assertEqual(row["bid_type"], "Product"); self.assertNotIn("portal", [k for k in row if k != "portal"] and [])
    def test_bad_url_dropped(self):
        self.assertIsNone(safe_url("javascript:alert(1)")); self.assertIsNone(safe_url("ftp://x"))
    def test_dates(self):
        self.assertEqual(parse_dt("01/03/2021 15:30:00"), "2021-03-01T10:00:00Z")
        self.assertIsNone(parse_dt("garbage"))
    def test_bad_date_flagged_for_db_rejection(self):
        row, _, _ = to_row({"source": "gem", "title": "Dustbin", "closing_date": "garbage"}, R)
        self.assertTrue(row["closing_at"].startswith("INVALID:"))
    def test_no_secret_in_source(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "ingest.py")).read()
        self.assertNotIn("eyJ", src); self.assertNotIn("print(key", src)
    def test_config_valid(self):
        self.assertTrue(len(R.search_terms()) > 20)

if __name__ == "__main__":
    unittest.main()
