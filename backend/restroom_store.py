from __future__ import annotations

import math
from typing import Any

import psycopg


RESTROOM_SELECT_SQL = """
SELECT
    id,
    building_name,
    floor_or_area,
    rooms,
    restroom_type,
    multi_user_stalls,
    has_shower,
    staff_only_any,
    notes,
    address,
    formatted_address_google,
    latitude,
    longitude,
    latitude_google,
    longitude_google,
    place_id,
    geocode_method,
    within_campus_bbox,
    google_maps_url,
    google_directions_url
FROM public.restrooms
"""


def load_restrooms_from_db(db_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(RESTROOM_SELECT_SQL)
            return list(cur.fetchall())


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using the Haversine formula."""
    earth_radius_miles = 3959

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) * math.sin(delta_lat / 2)
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2)
        * math.sin(delta_lon / 2)
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_miles * c


def calculate_walking_eta(distance_miles: float) -> int:
    walking_speed_mph = 3.0
    return max(1, int((distance_miles / walking_speed_mph) * 60))


def generate_natural_summary(restroom_data: dict[str, Any]) -> str:
    try:
        building = restroom_data["building_name"]
        restroom_type = restroom_data.get("restroom_type", "restroom").replace("-", " ").title()
        floor_info = (
            f" on {restroom_data.get('floor_or_area')}"
            if restroom_data.get("floor_or_area")
            else ""
        )

        features: list[str] = []
        if restroom_data.get("multi_user_stalls"):
            stalls = int(restroom_data["multi_user_stalls"])
            features.append(f"{stalls} stalls")

        if restroom_data.get("has_shower"):
            features.append("shower available")

        if restroom_data.get("staff_only_any"):
            features.append("staff access only")

        feature_text = f" with {', '.join(features)}" if features else ""
        summary = f"{restroom_type} restroom in {building}{floor_info}{feature_text}."

        notes = restroom_data.get("notes")
        if notes and str(notes).strip():
            summary += f" {notes}"

        return summary
    except Exception:
        building = restroom_data.get("building_name", "Building")
        return f"Restroom facilities available in {building}."


def search_restrooms(
    rows: list[dict[str, Any]],
    *,
    latitude: float,
    longitude: float,
    radius_miles: float,
    limit: int = 20,
    group_limit: int = 10,
) -> list[dict[str, Any]]:
    candidate_restrooms: list[tuple[dict[str, Any], float]] = []

    for restroom in rows:
        if not restroom.get("within_campus_bbox", True):
            continue

        row_lat = restroom.get("latitude_google")
        row_lon = restroom.get("longitude_google")
        if row_lat is None or row_lon is None:
            continue

        distance = calculate_distance(latitude, longitude, float(row_lat), float(row_lon))
        if distance <= radius_miles:
            candidate_restrooms.append((restroom, distance))

    candidate_restrooms.sort(key=lambda item: item[1])
    candidate_restrooms = candidate_restrooms[:limit]

    building_groups: dict[tuple[str, str], dict[str, Any]] = {}

    for restroom, distance in candidate_restrooms:
        restroom_address = restroom.get("formatted_address_google") or restroom.get("address", "")
        restroom_payload = {
            "id": str(restroom.get("id", restroom["building_name"])),
            "building_name": restroom["building_name"],
            "floor_or_area": restroom.get("floor_or_area"),
            "address": restroom_address,
            "latitude": float(restroom["latitude_google"]),
            "longitude": float(restroom["longitude_google"]),
            "rooms": restroom.get("rooms") or "",
            "restroom_type": restroom.get("restroom_type") or "restroom",
            "multi_user_stalls": restroom.get("multi_user_stalls"),
            "has_shower": bool(restroom.get("has_shower", False)),
            "staff_only_any": bool(restroom.get("staff_only_any", False)),
            "notes": restroom.get("notes"),
            "google_maps_url": restroom.get("google_maps_url") or "",
            "google_directions_url": restroom.get("google_directions_url") or "",
            "distance_miles": round(distance, 2),
            "eta_minutes": calculate_walking_eta(distance),
            "natural_summary": generate_natural_summary(restroom),
        }

        group_key = (restroom_payload["building_name"], restroom_payload["address"])
        if group_key not in building_groups:
            building_groups[group_key] = {
                "building_name": restroom_payload["building_name"],
                "address": restroom_payload["address"],
                "latitude": restroom_payload["latitude"],
                "longitude": restroom_payload["longitude"],
                "distance_miles": restroom_payload["distance_miles"],
                "eta_minutes": restroom_payload["eta_minutes"],
                "google_maps_url": restroom_payload["google_maps_url"],
                "restrooms": [],
            }

        building_groups[group_key]["restrooms"].append(restroom_payload)

    grouped_results = list(building_groups.values())
    grouped_results.sort(key=lambda group: group["distance_miles"])
    return grouped_results[:group_limit]
