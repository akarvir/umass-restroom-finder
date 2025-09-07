from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import math
import openai
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="UMass Restroom Locator API", version="1.0.0")

# CORS middleware to allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000","https://umass-restroom-radar.netlify.app"], # the frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: Optional[float] = 1.2  # Default 1.2 miles radius (roughly 2km)

class RestroomInfo(BaseModel):
    id: str
    building_name: str
    floor_or_area: Optional[str]
    address: str
    latitude: float
    longitude: float
    rooms: Optional[str] = None
    restroom_type: str # single-user, multi-user
    multi_user_stalls: Optional[float]
    has_shower: bool
    staff_only_any: bool
    notes: Optional[str]
    google_maps_url: str
    google_directions_url: str
    distance_miles: float
    eta_minutes: int
    natural_summary: str

class LocationGroup(BaseModel): # one of many snippets on the frontend
    building_name: str
    address: str
    latitude: float
    longitude: float
    distance_miles: float
    eta_minutes: int
    google_maps_url: str
    restrooms: List[RestroomInfo]

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula."""
    R = 3959  # Earth's radius in miles (changed from kilometers)
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) * math.sin(delta_lon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def calculate_walking_eta(distance_miles: float) -> int:
    """Calculate walking ETA in minutes (assuming 3 mph walking speed)."""
    walking_speed_mph = 3.0
    return max(1, int((distance_miles / walking_speed_mph) * 60))

def generate_natural_summary(restroom_data: dict) -> str:
    """Generate a simple, fast natural language summary without AI."""
    try:
        building = restroom_data['building_name']
        restroom_type = restroom_data['restroom_type'].replace('-', ' ').title()
        floor_info = f" on {restroom_data.get('floor_or_area')}" if restroom_data.get('floor_or_area') else ""
        
        # Build description based on features
        features = []
        if restroom_data.get('multi_user_stalls'):
            stalls = int(restroom_data['multi_user_stalls'])
            features.append(f"{stalls} stalls")
        
        if restroom_data.get('has_shower'):
            features.append("shower available")
            
        if restroom_data.get('staff_only_any'):
            features.append("staff access only")
        
        # Create summary
        feature_text = f" with {', '.join(features)}" if features else ""
        summary = f"{restroom_type} restroom in {building}{floor_info}{feature_text}."
        
        # Add notes if available
        if restroom_data.get('notes') and restroom_data['notes'].strip():
            summary += f" {restroom_data['notes']}"
            
        return summary
        
    except Exception as e:
        # Ultimate fallback
        building = restroom_data.get('building_name', 'Building')
        return f"Restroom facilities available in {building}."

def generate_batch_summaries(restrooms_data: list) -> list:
    """Generate summaries for multiple restrooms in one AI call (optional enhancement)."""
    # For now, use the fast local generation
    return [generate_natural_summary(restroom) for restroom in restrooms_data]

@app.get("/")
async def root():
    return {"message": "UMass Restroom Locator API - When you gotta go, you gotta go!"}

@app.post("/search-restrooms", response_model=List[LocationGroup])
async def search_restrooms(location: LocationRequest):
    """Search for nearby restrooms based on user location."""
    try:
        # Query only necessary columns and filter by campus bbox for better performance
        response = supabase.table("restrooms").select(
            "id, building_name, floor_or_area, formatted_address_google, address, "
            "latitude_google, longitude_google, rooms, restroom_type, multi_user_stalls, "
            "has_shower, staff_only_any, notes, google_maps_url, google_directions_url"
        ).eq("within_campus_bbox", True).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="No restrooms found in database")
        
        # Pre-filter and calculate distances
        candidate_restrooms = []
        for restroom in response.data:
            if restroom['latitude_google'] and restroom['longitude_google']:
                distance = calculate_distance(
                    location.latitude, location.longitude,
                    float(restroom['latitude_google']), float(restroom['longitude_google'])
                )
                
                if distance <= location.radius_miles:
                    candidate_restrooms.append((restroom, distance))
        
        if not candidate_restrooms:
            raise HTTPException(status_code=404, detail="No restrooms found within the specified radius")
        
        # Sort by distance and limit early
        candidate_restrooms.sort(key=lambda x: x[1])
        candidate_restrooms = candidate_restrooms[:20] if len(candidate_restrooms) > 20 else candidate_restrooms # Limit to 20 closest for performance
        
        # Generate summaries and build response
        restrooms_with_distance = []
        for restroom, distance in candidate_restrooms:
            eta = calculate_walking_eta(distance)
            natural_summary = generate_natural_summary(restroom)
            
            restroom_info = RestroomInfo(
                id=str(restroom.get('id', restroom['building_name'])),
                building_name=restroom['building_name'],
                floor_or_area=restroom.get('floor_or_area'),
                address=restroom['formatted_address_google'] or restroom.get('address', ''),
                latitude=float(restroom['latitude_google']),
                longitude=float(restroom['longitude_google']),
                rooms=restroom.get('rooms', ''),
                restroom_type=restroom.get('restroom_type', 'restroom'),
                multi_user_stalls=restroom.get('multi_user_stalls'),
                has_shower=bool(restroom.get('has_shower', False)),
                staff_only_any=bool(restroom.get('staff_only_any', False)),
                notes=restroom.get('notes'),
                google_maps_url=restroom.get('google_maps_url', ''),
                google_directions_url=restroom.get('google_directions_url', ''),
                distance_miles=round(distance, 2),
                eta_minutes=eta,
                natural_summary=natural_summary
            )
            restrooms_with_distance.append(restroom_info)
        
        # Group restrooms by building
        building_groups = []
        for restroom in restrooms_with_distance:
                building_group = {
                    'building_name': restroom.building_name,
                    'address': restroom.address,
                    'latitude': restroom.latitude,
                    'longitude': restroom.longitude,
                    'distance_miles': restroom.distance_miles,
                    'eta_minutes': restroom.eta_minutes,
                    'google_maps_url': restroom.google_maps_url,
                    'restrooms': []
                }
                building_group['restrooms'].append(restroom)
                building_groups.append(building_group)
        
        # Convert to list (already sorted by distance)
        location_groups = [
            LocationGroup(**group_data)
            for group_data in building_groups
        ]
        
        return location_groups[:10] if len(location_groups) > 10 else location_groups # Return top 10 closest locations
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching restrooms: {str(e)}")

async def generate_ai_summary_batch(restrooms_data: list) -> list:
    """Generate AI summaries for multiple restrooms in one call for better performance."""
    try:
        if not restrooms_data:
            return []
            
        # Create a batch prompt for multiple restrooms
        prompt = "Generate brief, friendly descriptions for these restroom locations (1 sentence each):\n\n"
        for i, restroom in enumerate(restrooms_data):
            prompt += f"{i+1}. {restroom['building_name']}"
            if restroom.get('floor_or_area'):
                prompt += f" - {restroom['floor_or_area']}"
            prompt += f" ({restroom.get('restroom_type', 'restroom')})"
            if restroom.get('multi_user_stalls'):
                prompt += f" - {int(restroom['multi_user_stalls'])} stalls"
            if restroom.get('has_shower'):
                prompt += " - with shower"
            prompt += "\n"
        
        prompt += "\nFormat: Just return numbered descriptions, one per line."
        
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Faster and cheaper model
            messages=[{"role": "user", "content": prompt}],
            max_tokens=len(restrooms_data) * 30,  # Scale with number of restrooms
            temperature=0.5
        )
        
        summaries = response.choices[0].message.content.strip().split('\n')
        # Clean up and match with restrooms
        clean_summaries = []
        for i, summary in enumerate(summaries):
            clean_summary = summary.strip()
            # Remove numbering if present
            if clean_summary.startswith(f"{i+1}."):
                clean_summary = clean_summary[len(f"{i+1}."):].strip()
            clean_summaries.append(clean_summary)
        
        # Ensure we have the right number of summaries
        while len(clean_summaries) < len(restrooms_data):
            clean_summaries.append("Clean restroom facilities available.")
            
        return clean_summaries[:len(restrooms_data)]
        
    except Exception as e:
        print(f"AI summary generation failed: {e}")
        # Fallback to fast generation
        return [generate_natural_summary(restroom) for restroom in restrooms_data]

@app.post("/search-restrooms-ai", response_model=List[LocationGroup])
async def search_restrooms_with_ai(location: LocationRequest):
    """Search for nearby restrooms with AI-generated descriptions (slower but richer)."""
    try:
        # Use the same search logic but with AI summaries
        response = supabase.table("restrooms").select(
            "id, building_name, floor_or_area, formatted_address_google, address, "
            "latitude_google, longitude_google, rooms, restroom_type, multi_user_stalls, "
            "has_shower, staff_only_any, notes, google_maps_url, google_directions_url"
        ).eq("within_campus_bbox", True).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="No restrooms found in database")
        
        # Pre-filter and calculate distances
        candidate_restrooms = []
        for restroom in response.data:
            if restroom['latitude_google'] and restroom['longitude_google']:
                distance = calculate_distance(
                    location.latitude, location.longitude,
                    float(restroom['latitude_google']), float(restroom['longitude_google'])
                )
                
                if distance <= location.radius_miles:
                    candidate_restrooms.append((restroom, distance))
        
        if not candidate_restrooms:
            return []
        
        # Sort by distance and limit
        candidate_restrooms.sort(key=lambda x: x[1])
        candidate_restrooms = candidate_restrooms[:15]  # Limit for AI processing
        
        # Generate AI summaries in batch
        restroom_data_for_ai = [restroom for restroom, _ in candidate_restrooms]
        ai_summaries = await generate_ai_summary_batch(restroom_data_for_ai)
        
        # Build response with AI summaries
        restrooms_with_distance = []
        for i, (restroom, distance) in enumerate(candidate_restrooms):
            eta = calculate_walking_eta(distance)
            natural_summary = ai_summaries[i] if i < len(ai_summaries) else generate_natural_summary(restroom)
            
            restroom_info = RestroomInfo(
                id=str(restroom.get('id', restroom['building_name'])),
                building_name=restroom['building_name'],
                floor_or_area=restroom.get('floor_or_area'),
                address=restroom['formatted_address_google'] or restroom.get('address', ''),
                latitude=float(restroom['latitude_google']),
                longitude=float(restroom['longitude_google']),
                rooms=restroom.get('rooms', ''),
                restroom_type=restroom.get('restroom_type', 'restroom'),
                multi_user_stalls=restroom.get('multi_user_stalls'),
                has_shower=bool(restroom.get('has_shower', False)),
                staff_only_any=bool(restroom.get('staff_only_any', False)),
                notes=restroom.get('notes'),
                google_maps_url=restroom.get('google_maps_url', ''),
                google_directions_url=restroom.get('google_directions_url', ''),
                distance_miles=round(distance, 2),
                eta_minutes=eta,
                natural_summary=natural_summary
            )
            restrooms_with_distance.append(restroom_info)
        
        # Group restrooms by building
        building_groups = {}
        for restroom in restrooms_with_distance:
            building_key = f"{restroom.building_name}_{restroom.address}"
            if building_key not in building_groups:
                building_groups[building_key] = {
                    'building_name': restroom.building_name,
                    'address': restroom.address,
                    'latitude': restroom.latitude,
                    'longitude': restroom.longitude,
                    'distance_miles': restroom.distance_miles,
                    'eta_minutes': restroom.eta_minutes,
                    'google_maps_url': restroom.google_maps_url,
                    'restrooms': []
                }
            building_groups[building_key]['restrooms'].append(restroom)
        
        # Convert to list
        location_groups = [
            LocationGroup(**group_data)
            for group_data in building_groups.values()
        ]
        
        return location_groups[:10]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching restrooms with AI: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "API is running smoothly"}
