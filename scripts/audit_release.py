#!/usr/bin/env python3
"""Bulk-check published Antalya food POIs against original extraction."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, parse_qs

FIELDS = {"osm_id", "name", "amenity", "latitude", "longitude", "route_url", "menu_url", "menu_verified", "website"}
ALLOWED = {"restaurant", "cafe", "fast_food"}
BLOCKED = {"instagram.com", "yemeksepeti.com"}
BBOX = (30.55, 36.80, 30.84, 36.96)


def readcsv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def forbidden_link(url):
    host = (urlparse(url).hostname or "").lower()
    return any(host == x or host.endswith("." + x) for x in BLOCKED)


def audit(root):
    all_rows = readcsv(root / "yemek_mekanlar.csv")
    published = readcsv(root / "yemek_yayin.csv")
    duplicates = readcsv(root / "muhtemel_mukerrerler.csv")
    geojson = json.loads((root / "yemek_yayin.geojson").read_text(encoding="utf-8"))
    origin = json.loads((root / "ozet.json").read_text(encoding="utf-8"))
    release = json.loads((root / "yayin_kalite_raporu.json").read_text(encoding="utf-8"))
    checks = {}

    def verify(key, ok):
        checks[key] = "PASS" if ok else "FAIL"

    ids = [r["osm_id"] for r in published]
    geofeatures = geojson.get("features", [])
    geo_by_id = {f.get("id"): f for f in geofeatures}
    idset = set(ids)
    verify("Kaynak OSM kimlikleri tekil", len(all_rows) == len({r["osm_id"] for r in all_rows}))
    verify("Yayın OSM kimlikleri tekil", len(ids) == len(idset))
    verify("Yayın ve kaynak sayısı raporla uyumlu", len(published) == release.get("named_published_map_points") and len(all_rows) == release.get("source_items_with_coordinates"))
    verify("GeoJSON ve CSV setleri birebir eşleşiyor", len(geo_by_id) == len(geofeatures) == len(ids) and set(geo_by_id) == idset)
    verify("CSV zorunlu sütunlar", not published or FIELDS <= published[0].keys())
    verify("Kaynakta isimsizler yayımlanmıyor", all(r["name"].strip() for r in published))
    verify("Yayınlanan kategoriler geçerli", all(r["amenity"] in ALLOWED for r in published))
    verify("Enlem ve boylam kutu içinde", all(BBOX[0] <= float(r["longitude"]) <= BBOX[2] and BBOX[1] <= float(r["latitude"]) <= BBOX[3] for r in published))
    verify("GeoJSON [boylam,enlem] eşleşmesi", all(
        abs(float(r["longitude"]) - geo_by_id[r["osm_id"]]["geometry"]["coordinates"][0]) < 1e-6
        and abs(float(r["latitude"]) - geo_by_id[r["osm_id"]]["geometry"]["coordinates"][1]) < 1e-6
        for r in published if r["osm_id"] in geo_by_id))
    verify("Yol tarifi URL hedefi doğru", all(
        urlparse(r["route_url"]).netloc == "www.google.com"
        and urlparse(r["route_url"]).path == "/maps/dir/"
        and parse_qs(urlparse(r["route_url"]).query).get("destination", [None])[0]
        == r["latitude"] + "," + r["longitude"] for r in published))
    verify("Menüler HTTPS adresi", all(not r["menu_url"] or urlparse(r["menu_url"]).scheme == "https" for r in published))
    verify("Menü varlığı doğrulamayla uyumlu", all(bool(r["menu_url"]) == (r["menu_verified"].lower() == "true") for r in published))
    verify("Menü sayısı raporla uyumlu", sum(bool(r["menu_url"]) for r in published) == release.get("published_menus_curated"))
    verify("Instagram / Yemeksepeti kartlarda yok", all(
        not forbidden_link(r.get("website", "")) and not forbidden_link(r.get("menu_url", ""))
        and not forbidden_link(r.get("menu_url_candidate", "")) for r in published))
    verify("Şüpheli mükerrerler yalnız inceleme adayı", all(d["action"] == "manual_review_do_not_auto_merge" for d in duplicates))
    verify("Şüpheli mükerrer kaynak kimlikleri var", all(d["osm_id_a"] in idset and d["osm_id_b"] in idset for d in duplicates))
    verify("Kategori dağılımı raporla aynı", dict(Counter(r["amenity"] for r in published)) == release.get("by_category"))
    verify("Kaynak OSM atfı", "OpenStreetMap" in origin.get("attribution", ""))
    result = {
        "tests": len(checks), "passed": sum(v == "PASS" for v in checks.values()),
        "failed": [k for k,v in checks.items() if v == "FAIL"], "checks": checks,
        "named_venues": len(published), "menus": sum(bool(r["menu_url"]) for r in published),
        "duplicate_pairs_review_only": len(duplicates), "automatic_deletions": 0,
    }
    (root / "toplu_test_raporu.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["failed"]:
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output"))
    audit(parser.parse_args().input)
