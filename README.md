# 🚽 UMass Restroom Locator

**When you gotta go, you gotta go.** Making navigation of UMass Amherst's 1500 acre campus a little easier.

A full-stack web application that helps UMass Amherst students, faculty, and visitors find the nearest restrooms on campus using their current location.

## Features

- 📍 **Location-based search**: Uses GPS to find restrooms near you
- 🗺️ **Google Maps integration**: Direct links to Google Maps and directions
- 🤖 **AI-powered descriptions**: Natural language summaries of each restroom
- 📱 **Responsive design**: Works on desktop and mobile devices
- 🚿 **Detailed info**: Shows amenities like showers, accessibility, number of stalls
- 🏢 **Building grouping**: Multiple restrooms per building are grouped together

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Supabase**: PostgreSQL database hosting
- **OpenAI API**: Natural language generation
- **Python libraries**: pandas, requests, python-dotenv

### Frontend
- **React**: Modern JavaScript framework with TypeScript
- **Axios**: HTTP client for API calls
- **CSS3**: Custom styling with gradients and animations

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 16+
- Supabase account
- OpenAI API key

### Backend Setup

1. **Install Python dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```bash
   cp env_example.txt .env
   ```
   
   Edit `.env` and add your credentials:
   ```
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_ANON_KEY=your_supabase_anon_key
   OPENAI_API_KEY=your_openai_api_key
   ```

3. **Create database table:**
   - Go to your Supabase dashboard
   - Run the SQL in `create_tables.sql` in the SQL editor

4. **Populate database:**
   ```bash
   python populate_database.py
   ```

5. **Start the backend server:**
   ```bash
   uvicorn main:app --reload
   ```
   
   The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm start
   ```
   
   The app will open at `http://localhost:3000`

## Usage

1. **Get your location**: Click "📍 Get My Location" to allow GPS access
2. **Search nearby**: Click "🚽 Search Restrooms Nearby" to find restrooms within 2km
3. **View results**: Browse restrooms grouped by building with detailed information
4. **Get directions**: Click "🧭 Get Directions" or "🗺️ See in Google Maps" for navigation

## API Endpoints

### `POST /search-restrooms`
Search for restrooms near a location.

**Request body:**
```json
{
  "latitude": 42.3898,
  "longitude": -72.5282,
  "radius_km": 2.0
}
```

**Response:**
```json
[
  {
    "building_name": "Du Bois Library",
    "address": "154 Hicks Way, Amherst, MA",
    "distance_km": 0.5,
    "eta_minutes": 6,
    "google_maps_url": "https://www.google.com/maps/...",
    "restrooms": [
      {
        "id": "dubois_1",
        "restroom_type": "single-user",
        "natural_summary": "Clean single-user restroom with accessibility features",
        "distance_km": 0.5,
        "eta_minutes": 6,
        "google_directions_url": "https://www.google.com/maps/dir/..."
      }
    ]
  }
]
```

## Data Source

The restroom data comes from a comprehensive survey of UMass Amherst campus buildings, geocoded using Google Places API for accurate locations and directions.

## Contributing

Feel free to submit issues and pull requests to improve the app!

## License

MIT License - feel free to use this for other university campuses!
