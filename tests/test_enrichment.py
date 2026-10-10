import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from enrich_menu_and_qa import build, duplicate_candidates, folded, menu_index


class EnrichmentTests(unittest.TestCase):
    def test_normalize_turkish_names(self):
        self.assertEqual(folded("İZMİR ŞİŞÇİ"), "izmir sisci")

    def test_close_duplicates_are_only_candidates(self):
        rows = [
            {"osm_id": "node/1", "name": "Üzüm Cafe", "latitude": "36.87", "longitude": "30.60"},
            {"osm_id": "node/2", "name": "Üzüm Cafe", "latitude": "36.87005", "longitude": "30.60003"},
            {"osm_id": "node/3", "name": "Üzüm Cafe", "latitude": "36.92", "longitude": "30.75"},
        ]
        dupes = duplicate_candidates(rows)
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]["action"], "manual_review_do_not_auto_merge")

    def test_rejects_menu_that_points_to_different_osm_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "src"
            out = root / "release"
            source.mkdir()
            with (source / "yemek_mekanlar.csv").open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["osm_id", "name", "amenity", "latitude", "longitude",
                                                  "menu_url_candidate", "menu_verified", "route_url"])
                w.writeheader()
                w.writerow({"osm_id": "node/20", "name": "Gerçek Lokanta",
                            "amenity": "restaurant", "latitude": "36.87", "longitude": "30.63"})
            (source / "yemek_mekanlar.geojson").write_text(json.dumps({
                "type": "FeatureCollection", "features": [{
                    "type": "Feature", "id": "node/20",
                    "geometry": {"type": "Point", "coordinates": [30.63, 36.87]},
                    "properties": {"osm_id": "node/20", "name": "Gerçek Lokanta"}
                }]
            }), encoding="utf-8")
            menus = root / "menus.json"
            menus.write_text(json.dumps({"schema_version": 1, "records": [{
                "osm_id": "node/20", "expected_osm_name": "Başka Lokanta",
                "menu_url": "https://example.com/menu", "menu_type": "official_html",
                "checked_on": "2026-10-11"}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                build(source, out, menus)

    def test_rejects_restricted_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            fn = Path(temp) / "menus.json"
            fn.write_text(json.dumps({"schema_version": 1, "records": [{
                "osm_id": "node/1", "expected_osm_name": "Test",
                "menu_url": "https://www.yemeksepeti.com/restaurant/test",
                "menu_type": "external_menu_page"}]}))
            with self.assertRaises(AssertionError):
                menu_index(fn)


if __name__ == "__main__":
    unittest.main()
