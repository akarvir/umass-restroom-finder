
"""
Geocode UMass Amherst building list with Google (Places + Geocoding) and emit
explicit Google *Directions* links (destination prefilled).

Usage:
  python geocode_google_v2.py --in umass_restrooms_dataset.csv --out umass_restrooms_dataset_google.csv

Adds columns:
  - place_id
  - formatted_address_google
  - latitude_google, longitude_google
  - google_maps_url               # canonical place URL
  - google_directions_url         # explicit directions URL (destination set; mode=walking)
  - geocode_method                # 'places_findplace' or 'geocode_address'
  - within_campus_bbox            # sanity flag
"""
import os, time, json, argparse
from typing import Dict, Any, Optional
import pandas as pd
import requests
from dotenv import load_dotenv

CAMPUS_LAT = 42.3899
CAMPUS_LNG = -72.5280
CAMPUS_RADIUS_METERS = 2200

PLACES_FIND_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

def backoff_sleep(attempt: int):
    secs = min(60, (2 ** attempt) + (0.1 * attempt))
    time.sleep(secs)

def is_within_bbox(lat: float, lng: float) -> bool:
    return (42.375 <= lat <= 42.405) and (-72.545 <= lng <= -72.510)

def directions_url(lat: float, lng: float, place_id: Optional[str]) -> str:
    base = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}&travelmode=walking"
    if place_id:
        base += f"&destination_place_id={place_id}"
    return base

def maps_search_url(lat: float, lng: float, place_id: Optional[str]) -> str:
    if place_id:
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={place_id}"
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"

def find_place(session: requests.Session, api_key: str, query: str) -> Optional[Dict[str, Any]]:
    params = {
        "key": api_key,
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id,name,geometry,formatted_address",
        "locationbias": f"circle:{CAMPUS_RADIUS_METERS}@{CAMPUS_LAT},{CAMPUS_LNG}",
        "language": "en",
    }
    attempt = 0
    while True:
        resp = session.get(PLACES_FIND_URL, params=params, timeout=20)
        if resp.status_code >= 500:
            attempt += 1
            backoff_sleep(attempt); continue
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "OK":
            cands = data.get("candidates", [])
            if not cands: return None
            inside = [c for c in cands if "geometry" in c and "location" in c["geometry"]
                      and is_within_bbox(c["geometry"]["location"]["lat"], c["geometry"]["location"]["lng"])]
            return (inside or cands)[0]
        if status in ("ZERO_RESULTS", "NOT_FOUND"):
            return None
        if status in ("OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"):
            attempt += 1; backoff_sleep(attempt); continue
        return None

def place_details(session: requests.Session, api_key: str, place_id: str) -> Optional[Dict[str, Any]]:
    params = {"key": api_key, "place_id": place_id, "fields": "url,geometry,formatted_address,name"}
    attempt = 0
    while True:
        resp = session.get(PLACES_DETAILS_URL, params=params, timeout=20)
        if resp.status_code >= 500:
            attempt += 1; backoff_sleep(attempt); continue
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "OK": return data.get("result", {})
        if status in ("OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"):
            attempt += 1; backoff_sleep(attempt); continue
        if status in ("ZERO_RESULTS", "NOT_FOUND"): return None
        return None

def geocode_address(session: requests.Session, api_key: str, address: str) -> Optional[Dict[str, Any]]:
    params = {
        "key": api_key,
        "address": address,
        "bounds": f"{CAMPUS_LAT-0.02},{CAMPUS_LNG-0.02}|{CAMPUS_LAT+0.02},{CAMPUS_LNG+0.02}",
        "language": "en",
        "region": "us",
    }
    attempt = 0
    while True:
        resp = session.get(GEOCODE_URL, params=params, timeout=20)
        if resp.status_code >= 500:
            attempt += 1; backoff_sleep(attempt); continue
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "OK":
            results = data.get("results", [])
            return results[0] if results else None
        if status in ("OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"):
            attempt += 1; backoff_sleep(attempt); continue
        if status in ("ZERO_RESULTS", "NOT_FOUND"): return None
        return None

def best_guess(session: requests.Session, api_key: str, name: str, address: Optional[str]) -> Optional[Dict[str, Any]]:
    queries = [f"{name}, UMass Amherst, Amherst, MA"]
    if not any(s in name.lower() for s in ["hall","building","center","lab","library","house","commons","station"]):
        queries.append(f"{name} building, UMass Amherst, Amherst, MA")
    for q in queries:
        cand = find_place(session, api_key, q)
        if cand:
            loc = cand["geometry"]["location"]
            res = {
                "method": "places_findplace",
                "place_id": cand.get("place_id"),
                "name": cand.get("name", name),
                "formatted_address": cand.get("formatted_address", ""),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
            }
            det = place_details(session, api_key, res["place_id"]) if res["place_id"] else None
            if det:
                res["formatted_address"] = det.get("formatted_address", res["formatted_address"])
                res["name"] = det.get("name", res["name"])
            return res
    if address:
        geo = geocode_address(session, api_key, address)
        if geo and "geometry" in geo:
            loc = geo["geometry"]["location"]
            return {
                "method": "geocode_address",
                "place_id": None,
                "name": name,
                "formatted_address": geo.get("formatted_address", address),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
            }
    return None

def main():
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_csv", required=True)
    parser.add_argument("--out", dest="out_csv", required=True)
    parser.add_argument("--cache", dest="cache_path", default="geocode_cache.json")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Missing GOOGLE_MAPS_API_KEY", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(args.in_csv)
    by_bldg = df.groupby("building_name").agg({"address":"first"}).reset_index()

    cache: Dict[str, Any] = {}
    if os.path.exists(args.cache_path):
        try:
            cache = json.load(open(args.cache_path))
        except Exception:
            cache = {}

    session = requests.Session()
    results: Dict[str, Dict[str, Any]] = {}

    for _, row in by_bldg.iterrows():
        name = str(row["building_name"]).strip()
        address = str(row["address"]) if isinstance(row["address"], str) and row["address"] else None

        if name in cache:
            results[name] = cache[name]
            continue

        print(f"Resolving: {name} ...", flush=True)
        info = best_guess(session, api_key, name, address)
        if info and isinstance(info.get("lat"), (int, float)) and isinstance(info.get("lng"), (int, float)):
            info["within_campus_bbox"] = bool(is_within_bbox(info["lat"], info["lng"]))
            results[name] = info
        else:
            results[name] = {"error": "not_found"}

        cache[name] = results[name]
        json.dump(cache, open(args.cache_path, "w"), indent=2)
        time.sleep(0.25)

    out = df.copy()
    out["place_id"] = out["building_name"].map(lambda b: results.get(b, {}).get("place_id"))
    out["formatted_address_google"] = out["building_name"].map(lambda b: results.get(b, {}).get("formatted_address"))
    out["latitude_google"] = out["building_name"].map(lambda b: results.get(b, {}).get("lat"))
    out["longitude_google"] = out["building_name"].map(lambda b: results.get(b, {}).get("lng"))
    out["google_maps_url"] = out["building_name"].map(
        lambda b: (None if results.get(b, {}).get("error")
                   else (lambda lat,lng,pid: (None if (lat is None or lng is None) else
                       ("https://www.google.com/maps/search/?api=1&query=%s,%s%s" % (
                           lat, lng, f"&query_place_id={pid}" if pid else ""))))(
                           results.get(b, {}).get("lat"), results.get(b, {}).get("lng"), results.get(b, {}).get("place_id")
                   )
        )
    )
    out["google_directions_url"] = out["building_name"].map(
        lambda b: (None if results.get(b, {}).get("error")
                   else (lambda lat,lng,pid: (None if (lat is None or lng is None) else
                       ("https://www.google.com/maps/dir/?api=1&destination=%s,%s&travelmode=walking%s" % (
                           lat, lng, f"&destination_place_id={pid}" if pid else ""))))(
                           results.get(b, {}).get("lat"), results.get(b, {}).get("lng"), results.get(b, {}).get("place_id")
                   )
        )
    )
    out["geocode_method"] = out["building_name"].map(lambda b: results.get(b, {}).get("method"))
    out["within_campus_bbox"] = out["building_name"].map(lambda b: results.get(b, {}).get("within_campus_bbox"))

    out.to_csv(args.out_csv, index=False)
    print(f"Wrote enriched dataset → {args.out_csv}")

if __name__ == "__main__":
    main()
