#!/usr/bin/env python3
"""Turn an Osmium GeoJSON extract into audited Antalya food POI records."""
import argparse
import csv
import datetime
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote, urlsplit

from shapely.geometry import shape

BOUNDS = (30.55, 36.80, 30.84, 36.96)  # west, south, east, north
CATEGORIES = {"restaurant", "cafe", "fast_food"}
SOURCE = "https://download.geofabrik.de/europe/turkey-latest.osm.pbf"
FIELDS = ("osm_id", "name", "amenity", "latitude", "longitude", "cuisine",
          "menu_url_candidate", "menu_verified", "route_url", "website")


def valid_link(raw):
    if not isinstance(raw, str):
        return ""
    value = raw.strip()
    if not value or any(c.isspace() for c in value):
        return ""
    parts = urlsplit(value)
    host = (parts.hostname or "").casefold()
    forbidden = ("instagram.com", "yemeksepeti.com")
    if any(host == domain or host.endswith("." + domain) for domain in forbidden):
        return ""
    return value if parts.scheme in ("http", "https") and host and not parts.username else ""


def point_for_geometry(geometry):
    if not isinstance(geometry, dict):
        return None
    try:
        geom = shape(geometry)
        if geom.is_empty:
            return None
        pt = geom if geom.geom_type == "Point" else geom.representative_point()
        lon, lat = float(pt.x), float(pt.y)
        if BOUNDS[0] <= lon <= BOUNDS[2] and BOUNDS[1] <= lat <= BOUNDS[3]:
            return round(lat, 7), round(lon, 7)
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def process_features(features):
    records = {}
    checks = Counter()
    for feat in features:
        checks["exported_features"] += 1
        props = feat.get("properties") or {}
        if props.get("amenity") not in CATEGORIES:
            checks["not_food_category"] += 1
            continue
        obj_type = props.get("@type")
        obj_id = props.get("@id")
        if obj_type not in ("node", "way", "relation") or not isinstance(obj_id, int):
            checks["missing_source_id"] += 1
            continue
        osm_id = f"{obj_type}/{obj_id}"
        pt = point_for_geometry(feat.get("geometry"))
        if pt is None:
            checks["missing_or_outside_coordinates"] += 1
            continue
        lat, lon = pt
        name = str(props.get("name") or props.get("name:tr") or "").strip()
        if not name:
            checks["unnamed"] += 1

        website = valid_link(props.get("website") or props.get("contact:website"))
        menu = valid_link(props.get("website:menu") or props.get("menu:website")
                          or props.get("contact:menu"))
        candidate = {
            "osm_id": osm_id,
            "name": name,
            "amenity": props["amenity"],
            "latitude": lat,
            "longitude": lon,
            "cuisine": str(props.get("cuisine") or ""),
            "menu_url_candidate": menu,
            "menu_verified": False,
            "route_url": "https://www.google.com/maps/dir/?api=1&destination="
                         + quote(f"{lat},{lon}", safe=""),
            "website": website,
        }
        previous = records.get(osm_id)
        if previous is not None:
            checks["repeated_source_id"] += 1
            # When Osmium emits both a line and polygon for the same way,
            # retain the record with more populated values.
            old_score = sum(bool(previous[k]) for k in ("name", "cuisine", "website", "menu_url_candidate"))
            new_score = sum(bool(candidate[k]) for k in ("name", "cuisine", "website", "menu_url_candidate"))
            if new_score > old_score:
                records[osm_id] = candidate
        else:
            records[osm_id] = candidate
    result = sorted(records.values(), key=lambda x: (x["name"].casefold(), x["osm_id"]))
    return result, checks


def export(input_file, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    with input_file.open(encoding="utf-8") as f:
        payload = json.load(f)
    if payload.get("type") != "FeatureCollection":
        raise ValueError("Beklenen GeoJSON FeatureCollection bulunamadı")
    records, checks = process_features(payload.get("features", []))
    if not records:
        raise ValueError("Hiçbir koordinatlı yemek mekânı çıkarılamadı; çıktı üretilmedi")
    with (out_dir / "yemek_mekanlar.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    features = []
    for item in records:
        if not item["name"]:
            continue  # unnamed records retained in CSV for data QA, not shown as pins
        properties = {k: v for k, v in item.items() if k not in ("latitude", "longitude")}
        features.append({"type": "Feature", "id": item["osm_id"],
                         "geometry": {"type": "Point",
                                      "coordinates": [item["longitude"], item["latitude"]]},
                         "properties": properties})
    with (out_dir / "yemek_mekanlar.geojson").open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
    stats = {
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": SOURCE, "source_license": "ODbL 1.0",
        "attribution": "© OpenStreetMap contributors",
        "bbox_west_south_east_north": BOUNDS,
        "osm_id_count": len(records),
        "named_map_points": len(features),
        "by_category": dict(Counter(r["amenity"] for r in records)),
        "menu_candidates_not_verified": sum(bool(r["menu_url_candidate"]) for r in records),
        "checks": dict(checks),
    }
    with (out_dir / "ozet.json").open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("output"))
    args = parser.parse_args()
    export(args.input, args.output)
