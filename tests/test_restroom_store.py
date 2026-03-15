from fastapi.testclient import TestClient


def _sample_row(
    *,
    id: str,
    building_name: str,
    latitude_google: float,
    longitude_google: float,
    floor_or_area: str | None = None,
    rooms: str | None = None,
    restroom_type: str = "single-user",
    multi_user_stalls: int | None = None,
    has_shower: bool = False,
    staff_only_any: bool = False,
    notes: str | None = None,
) -> dict:
    return {
        "id": id,
        "building_name": building_name,
        "floor_or_area": floor_or_area,
        "formatted_address_google": f"{building_name} Address",
        "address": f"{building_name} Address",
        "latitude_google": latitude_google,
        "longitude_google": longitude_google,
        "rooms": rooms,
        "restroom_type": restroom_type,
        "multi_user_stalls": multi_user_stalls,
        "has_shower": has_shower,
        "staff_only_any": staff_only_any,
        "notes": notes,
        "google_maps_url": f"https://maps.example/{id}",
        "google_directions_url": f"https://directions.example/{id}",
        "within_campus_bbox": True,
    }


def test_search_restrooms_uses_preloaded_store_and_groups_by_building():
    from backend.main import create_app

    rows = [
        _sample_row(
            id="a",
            building_name="Campus Center",
            latitude_google=42.3910,
            longitude_google=-72.5260,
            floor_or_area="Floor 1",
            rooms="101",
            notes="Near the entrance",
        ),
        _sample_row(
            id="b",
            building_name="Campus Center",
            latitude_google=42.3910,
            longitude_google=-72.5260,
            floor_or_area="Floor 2",
            rooms="202",
            restroom_type="multi-user",
            multi_user_stalls=3,
        ),
        _sample_row(
            id="c",
            building_name="Library",
            latitude_google=42.3995,
            longitude_google=-72.5400,
        ),
    ]

    app = create_app(initial_restroom_rows=rows)
    client = TestClient(app)

    response = client.post(
        "/search-restrooms",
        json={
            "latitude": 42.3911,
            "longitude": -72.5261,
            "radius_miles": 0.5,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["building_name"] == "Campus Center"
    assert payload[0]["address"] == "Campus Center Address"
    assert payload[0]["google_maps_url"] == "https://maps.example/a"
    assert len(payload[0]["restrooms"]) == 2

    first_restroom = payload[0]["restrooms"][0]
    assert first_restroom["id"] == "a"
    assert first_restroom["building_name"] == "Campus Center"
    assert first_restroom["floor_or_area"] == "Floor 1"
    assert first_restroom["rooms"] == "101"
    assert first_restroom["restroom_type"] == "single-user"
    assert isinstance(first_restroom["distance_miles"], float)
    assert isinstance(first_restroom["eta_minutes"], int)
    assert first_restroom["natural_summary"].startswith("Single User restroom")


def test_search_restrooms_returns_404_when_store_has_no_matching_results():
    from backend.main import create_app

    app = create_app(
        initial_restroom_rows=[
            _sample_row(
                id="only",
                building_name="Far Building",
                latitude_google=42.4050,
                longitude_google=-72.5450,
            )
        ]
    )
    client = TestClient(app)

    response = client.post(
        "/search-restrooms",
        json={
            "latitude": 42.3911,
            "longitude": -72.5261,
            "radius_miles": 0.1,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No restrooms found within the specified radius"
