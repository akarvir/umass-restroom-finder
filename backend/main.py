from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

from backend.restroom_store import generate_natural_summary, load_restrooms_from_db, search_restrooms


load_dotenv(Path(__file__).with_name(".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_URL = os.getenv("SUPABASE_DB_URL")

if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None


class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: Optional[float] = 1.2


class RestroomInfo(BaseModel):
    id: str
    building_name: str
    floor_or_area: Optional[str]
    address: str
    latitude: float
    longitude: float
    rooms: Optional[str] = None
    restroom_type: str
    multi_user_stalls: Optional[float]
    has_shower: bool
    staff_only_any: bool
    notes: Optional[str]
    google_maps_url: str
    google_directions_url: str
    distance_miles: float
    eta_minutes: int
    natural_summary: str


class LocationGroup(BaseModel):
    building_name: str
    address: str
    latitude: float
    longitude: float
    distance_miles: float
    eta_minutes: int
    google_maps_url: str
    restrooms: list[RestroomInfo]


async def generate_ai_summary_batch(restrooms_data: list[dict[str, Any]]) -> list[str]:
    if not restrooms_data:
        return []

    if openai_client is None:
        return [generate_natural_summary(restroom) for restroom in restrooms_data]

    try:
        prompt = "Generate brief, friendly descriptions for these restroom locations (1 sentence each):\n\n"
        for index, restroom in enumerate(restrooms_data, start=1):
            prompt += f"{index}. {restroom['building_name']}"
            if restroom.get("floor_or_area"):
                prompt += f" - {restroom['floor_or_area']}"
            prompt += f" ({restroom.get('restroom_type', 'restroom')})"
            if restroom.get("multi_user_stalls"):
                prompt += f" - {int(restroom['multi_user_stalls'])} stalls"
            if restroom.get("has_shower"):
                prompt += " - with shower"
            prompt += "\n"

        prompt += "\nFormat: Just return numbered descriptions, one per line."

        response = openai_client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
        )
        text = response.output_text.strip()
        summaries = text.split("\n")

        clean_summaries = []
        for index, summary in enumerate(summaries, start=1):
            clean_summary = summary.strip()
            if clean_summary.startswith(f"{index}."):
                clean_summary = clean_summary[len(f"{index}.") :].strip()
            clean_summaries.append(clean_summary)

        while len(clean_summaries) < len(restrooms_data):
            clean_summaries.append("Clean restroom facilities available.")

        return clean_summaries[: len(restrooms_data)]
    except Exception:
        return [generate_natural_summary(restroom) for restroom in restrooms_data]


def _build_lifespan(initial_restroom_rows: list[dict[str, Any]] | None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if initial_restroom_rows is not None:
            app.state.restroom_rows = initial_restroom_rows
        elif DB_URL:
            app.state.restroom_rows = load_restrooms_from_db(DB_URL)
        elif not hasattr(app.state, "restroom_rows"):
            app.state.restroom_rows = []
        yield

    return lifespan


def create_app(initial_restroom_rows: list[dict[str, Any]] | None = None) -> FastAPI:
    app = FastAPI(
        title="UMass Restroom Locator API",
        version="1.0.0",
        lifespan=_build_lifespan(initial_restroom_rows),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://umass-restroom-radar.netlify.app",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.restroom_rows = initial_restroom_rows or []

    @app.get("/")
    async def root():
        return {"message": "UMass Restroom Locator API - When you gotta go, you gotta go!"}

    @app.post("/search-restrooms", response_model=list[LocationGroup])
    async def search_restrooms_route(location: LocationRequest, request: Request):
        rows = getattr(request.app.state, "restroom_rows", [])
        if not rows:
            raise HTTPException(status_code=404, detail="No restrooms found in database")

        matches = search_restrooms(
            rows,
            latitude=location.latitude,
            longitude=location.longitude,
            radius_miles=location.radius_miles,
        )
        if not matches:
            raise HTTPException(
                status_code=404,
                detail="No restrooms found within the specified radius",
            )
        return matches

    @app.post("/search-restrooms-ai", response_model=list[LocationGroup])
    async def search_restrooms_with_ai(location: LocationRequest, request: Request):
        rows = getattr(request.app.state, "restroom_rows", [])
        if not rows:
            raise HTTPException(status_code=404, detail="No restrooms found in database")

        matches = search_restrooms(
            rows,
            latitude=location.latitude,
            longitude=location.longitude,
            radius_miles=location.radius_miles,
            limit=15,
        )
        if not matches:
            return []

        flattened_restrooms: list[dict[str, Any]] = []
        for group in matches:
            flattened_restrooms.extend(group["restrooms"])

        summaries = await generate_ai_summary_batch(flattened_restrooms)
        for restroom, summary in zip(flattened_restrooms, summaries):
            restroom["natural_summary"] = summary

        return matches[:10]

    @app.get("/health")
    async def health_check():
        row_count = len(getattr(app.state, "restroom_rows", []))
        return {"status": "healthy", "message": "API is running smoothly", "row_count": row_count}

    return app


app = create_app()
