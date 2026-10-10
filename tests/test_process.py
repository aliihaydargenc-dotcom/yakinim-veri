import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from process_geojson import point_for_geometry, process_features, valid_link


class FoodExportTests(unittest.TestCase):
    def test_point_and_route(self):
        data = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [30.70, 36.88]},
                 "properties": {"@type": "node", "@id": 10, "amenity": "restaurant",
                                "name": "Örnek Restoran", "website:menu": "https://example.com/menu"}}]
        rows, stats = process_features(data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["osm_id"], "node/10")
        self.assertEqual(rows[0]["name"], "Örnek Restoran")
        self.assertTrue(rows[0]["route_url"].startswith("https://www.google.com/maps/dir/"))
        self.assertFalse(rows[0]["menu_verified"])

    def test_outside_is_not_included(self):
        data = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [31.10, 36.88]},
                 "properties": {"@type": "node", "@id": 10, "amenity": "cafe"}}]
        rows, stats = process_features(data)
        self.assertFalse(rows)
        self.assertEqual(stats["missing_or_outside_coordinates"], 1)

    def test_malformed_and_missing_ids_are_rejected(self):
        data = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [30.70, 36.88]},
                 "properties": {"amenity": "restaurant", "name": "No ID"}}]
        rows, stats = process_features(data)
        self.assertFalse(rows)
        self.assertEqual(stats["missing_source_id"], 1)

    def test_polygon_representative_point(self):
        poly = {"type": "Polygon", "coordinates": [[
            [30.65, 36.85], [30.66, 36.85], [30.66, 36.86],
            [30.65, 36.86], [30.65, 36.85]]]}
        result = point_for_geometry(poly)
        self.assertIsNotNone(result)
        self.assertGreater(result[0], 36.84)
        self.assertLess(result[1], 30.67)

    def test_duplicate_source_id(self):
        f = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [30.70, 36.88]},
             "properties": {"@type": "node", "@id": 11, "amenity": "fast_food", "name": "A"}}
        rows, stats = process_features([f, f])
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats["repeated_source_id"], 1)

    def test_url_safety(self):
        self.assertEqual(valid_link("javascript:alert(1)"), "")
        self.assertEqual(valid_link("https://example.com/menu.pdf"), "https://example.com/menu.pdf")


if __name__ == "__main__":
    unittest.main()
