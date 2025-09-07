import React, { useState } from 'react';
import axios from 'axios';
import './RestroomLocator.css';

interface RestroomInfo {
  id: string;
  building_name: string;
  floor_or_area?: string;
  address: string;
  latitude: number;
  longitude: number;
  rooms: string;
  restroom_type: string;
  multi_user_stalls?: number;
  has_shower: boolean;
  staff_only_any: boolean;
  notes?: string;
  google_maps_url: string;
  google_directions_url: string;
  distance_miles: number;
  eta_minutes: number;
  natural_summary: string;
}

interface LocationGroup {
  building_name: string;
  address: string;
  latitude: number;
  longitude: number;
  distance_miles: number;
  eta_minutes: number;
  google_maps_url: string;
  restrooms: RestroomInfo[];
}

const RestroomLocator: React.FC = () => {
  const [userLocation, setUserLocation] = useState<{lat: number, lng: number} | null>(null); // this is not shown on the frontend, sent as part of LocationRequest
  const [isLoading, setIsLoading] = useState(false);
  const [locationGroups, setLocationGroups] = useState<LocationGroup[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [locationStatus, setLocationStatus] = useState<string>(''); // might be the 'Found 10 of the nearest locations'

  const getCurrentLocation = () => {
    setLocationStatus('Getting your location...');
    setError(null);
    
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by this browser');
      setLocationStatus('');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const location = {
          lat: position.coords.latitude,
          lng: position.coords.longitude
        };
        setUserLocation(location);
        setLocationStatus('📍 Location acquired successfully!');
      },
      (error) => {
        let errorMessage = 'Error getting location';
        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage = 'Location access denied by user';
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage = 'Location information unavailable';
            break;
          case error.TIMEOUT:
            errorMessage = 'Location request timed out';
            break;
        }
        setError(errorMessage);
        setLocationStatus('');
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000 // 5 minutes
      }
    );
  };

  const searchNearbyRestrooms = async () => {
    if (!userLocation) {
      setError('Please get your location first');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.post(process.env.REACT_APP_BACKEND_URL + '/search-restrooms', {
        latitude: userLocation.lat,
        longitude: userLocation.lng,
        radius_miles: 1.2
      }); // LocationRequest model format. 

      setLocationGroups(response.data);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Error searching for restrooms';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const openGoogleMaps = (url: string) => {
    window.open(url, '_blank');
  };

  return (
    <div className="restroom-locator">
      <div className="controls">
        <button 
          onClick={getCurrentLocation} 
          className="location-btn"
          disabled={isLoading}
        >
          📍 Get My Location
        </button>
        
        <button 
          onClick={searchNearbyRestrooms} 
          className="search-btn"
          disabled={!userLocation || isLoading}
        >
          {isLoading ? '🔄 Searching...' : 'Search Restrooms Nearby'}
        </button>
      </div>

      {locationStatus && (
        <div className="status-message">
          {locationStatus}
        </div>
      )}

      {error && (
        <div className="error-message">
          ❌ {error}
        </div>
      )}

      {locationGroups.length > 0 && (
        <div className="results">
          <h2>🎯 Found {locationGroups.length} of the nearest locations</h2>
          
          {locationGroups.map((group, groupIndex) => (
            <div key={groupIndex} className="location-group">
              <div className="location-header">
                <h3>{group.building_name}</h3>
                <div className="location-meta">
                  <span className="distance">📏 {group.distance_miles?.toFixed(2) || '0.00'} mi away</span>
                  <span className="eta">⏱️ {group.eta_minutes} min walk</span>
                </div>
              </div>
              
              <div className="address">📍 {group.address}</div>
              
              <div className="restrooms-list">
                {group.restrooms.map((restroom, restroomIndex) => (
                  <div key={restroomIndex} className="restroom-card">
                    <div className="restroom-header">
                      <div className="restroom-badges">
                        <span className="restroom-type">
                          {restroom.restroom_type.replace('-', ' ').toUpperCase()}
                        </span>
                        {restroom.restroom_type === 'single-user' && (
                          <span className="gender-inclusive">Gender-inclusive ✅</span>
                        )}
                      </div>
                      {restroom.floor_or_area && (
                        <span className="floor">📍 {restroom.floor_or_area}</span>
                      )}
                    </div>
                    
                    <div className="restroom-summary">
                      {restroom.natural_summary}
                    </div>
                    
                    <div className="restroom-details">
                      {restroom.rooms && (
                        <span className="rooms">🚪 Rooms: {restroom.rooms}</span>
                      )}
                      {restroom.multi_user_stalls && (
                        <span className="stalls">🚽 {restroom.multi_user_stalls} stalls</span>
                      )}
                      {restroom.has_shower && (
                        <span className="shower">🚿 Shower available</span>
                      )}
                      {restroom.staff_only_any && (
                        <span className="staff-only">👷 Staff only</span>
                      )}
                    </div>
                    
                    {restroom.notes && (
                      <div className="restroom-notes">
                        💡 {restroom.notes}
                      </div>
                    )}
                    
                    <button 
                      onClick={() => openGoogleMaps(restroom.google_directions_url)}
                      className="directions-btn primary"
                    >
                      🧭 Get Directions
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!isLoading && locationGroups.length === 0 && userLocation && ( // when userlocation is set, and locationgroups is by default [], this shows.
        <div className="no-results">
          No UMass restrooms found nearby. Try searching from a location on campus.
        </div>
      )}
    </div>
  );
};

export default RestroomLocator;
