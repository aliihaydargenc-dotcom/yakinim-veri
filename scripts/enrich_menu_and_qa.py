#!/usr/bin/env python3
"""Build a safe, named-POI release by joining curated menus on exact OSM ids."""
import argparse
import csv
import json
import math
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit


def folded(text):
    x = unicodedata.normalize("NFKD", str(text).replace("ı", "i").casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in x if not unicodedata.combining(c))))


def menu_index(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    menus = {}
    for item in data["records"]:
        key = item["osm_id"]
        url = item["menu_url"]
        parts = urlsplit(url)
        assert parts.scheme == "https" and parts.netloc and "@" not in parts.netloc
        assert not any(bad in parts.netloc.casefold() for bad in ("instagram", "yemeksepeti"))
        assert item["menu_type"] in ("official_html", "official_pdf", "external_menu_page")
        assert key not in menus, "Duplicate curated OSM identity"
        menus[key] = item
    return menus


def distance_m(a, b):
    lat1, lon1 = float(a["latitude"]), float(a["longitude"])
    lat2, lon2 = float(b["latitude"]), float(b["longitude"])
    delta_lat = (lat2 - lat1) * 111195.0
    delta_lon = (lon2 - lon1) * 111195.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(delta_lat, delta_lon)


def duplicate_candidates(rows, radius=80):
    result = []
    for i, a in enumerate(rows):
        na = folded(a["name"])
        if len(na) < 3:
            continue
        for b in rows[i + 1:]:
            if abs(float(a["latitude"]) - float(b["latitude"])) > .00073:
                continue
            nb = folded(b["name"])
            if len(nb) < 3:
                continue
            distance = distance_m(a, b)
            if distance > radius:
                continue
            sim = SequenceMatcher(None, na, nb).ratio()
            if sim < .80:
                continue
            result.append({
                "osm_id_a": a["osm_id"], "name_a": a["name"],
                "osm_id_b": b["osm_id"], "name_b": b["name"],
                "distance_m": round(distance, 1), "name_similarity": round(sim, 3),
                "action": "manual_review_do_not_auto_merge"
            })
    return sorted(result, key=lambda x: (x["distance_m"], x["osm_id_a"]))


def build(input_dir, output_dir, curated_path):
    output_dir.mkdir(parents=True, exist_ok=True)
    with (input_dir / "yemek_mekanlar.csv").open(encoding="utf-8-sig", newline="") as f:
        records = list(csv.DictReader(f))
    base = json.loads((input_dir / "yemek_mekanlar.geojson").read_text(encoding="utf-8"))
    menus = menu_index(curated_path)

    if len(records) != len({r["osm_id"] for r in records}):
        raise ValueError("Duplicate source OSM identities")
    by_id = {r["osm_id"]: r for r in records}
    if not menus.keys() <= by_id.keys():
        raise ValueError("Curated menu refers to an OSM id absent in latest extract")
    for osm_id, menu in menus.items():
        r = by_id[osm_id]
        if folded(r["name"]) != folded(menu["expected_osm_name"]):
            raise ValueError(f"OSM identity changed or menu name mismatch: {osm_id}")

    published = []
    for r in records:
        if not r["name"].strip():
            continue
        o = dict(r)
        o["menu_url"] = ""
        o["menu_source_type"] = ""
        o["menu_checked_at"] = ""
        o["menu_verified"] = "false"
        if r["osm_id"] in menus:
            match = menus[r["osm_id"]]
            o.update(menu_url=match["menu_url"],
                     menu_source_type=match["menu_type"],
                     menu_checked_at=match["checked_on"],
                     menu_verified="true")
        published.append(o)

    if len(published) != len(base["features"]):
        raise ValueError("Named CSV items do not match original GeoJSON features")
    approved = {r["osm_id"]: r for r in published}
    features = []
    for f in base["features"]:
        r = approved.get(f["id"])
        if not r:
            raise ValueError("GeoJSON contains missing or unnamed OSM record")
        f["properties"].update({
            "menu_url": r["menu_url"],
            "menu_verified": r["menu_verified"] == "true",
            "menu_source_type": r["menu_source_type"],
            "menu_checked_at": r["menu_checked_at"],
        })
        features.append(f)
    dupes = duplicate_candidates(published)

    fields = list(published[0].keys())
    with (output_dir / "yemek_yayin.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(published)
    (output_dir / "yemek_yayin.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8")

    with (output_dir / "muhtemel_mukerrerler.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["osm_id_a", "name_a", "osm_id_b", "name_b", "distance_m",
                  "name_similarity", "action"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(dupes)

    stats = {
        "source_items_with_coordinates": len(records),
        "named_published_map_points": len(published),
        "no_name_source_items": len(records) - len(published),
        "published_menus_curated": sum(bool(r["menu_url"]) for r in published),
        "menu_ids": sorted(menus.keys()),
        "unverified_source_menu_candidates": sum(bool(r["menu_url_candidate"]) for r in records),
        "possible_duplicate_pairs_review_only": len(dupes),
        "by_category": dict(Counter(r["amenity"] for r in published)),
        "no_rating_or_popularity_inferred": True,
        "source_attribution": "© OpenStreetMap contributors (ODbL)",
        "note": "This is an offline data artifact; not an app deployment or current-open claim."
    }
    (output_dir / "yayin_kalite_raporu.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("output"))
    ap.add_argument("--output", type=Path, default=Path("output"))
    ap.add_argument("--menus", type=Path, default=Path("data/menus_curated.json"))
    a = ap.parse_args()
    build(a.input, a.output, a.menus)
