import pandas as pd
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def populate_restrooms_database():
    """Populate Supabase database with restroom data from CSV."""
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("Error: Missing Supabase credentials in .env file")
        return
    
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Read the CSV file
    csv_path = "../umass_restrooms_dataset_google.csv"
    df = pd.read_csv(csv_path)
    
    # Clean and prepare data
    restrooms_data = []
    for _, row in df.iterrows():
        # Skip empty rows
        if pd.isna(row['building_name']) or row['building_name'].strip() == '':
            continue
            
        restroom_record = {
            'building_name': str(row['building_name']).strip(),
            'floor_or_area': str(row['floor_or_area']).strip() if pd.notna(row['floor_or_area']) else None,
            'address': str(row['address']).strip() if pd.notna(row['address']) else None,
            'latitude': float(row['latitude']) if pd.notna(row['latitude']) else None,
            'longitude': float(row['longitude']) if pd.notna(row['longitude']) else None,
            'rooms': str(row['rooms']).strip() if pd.notna(row['rooms']) else None,
            'restroom_type': str(row['restroom_type']).strip() if pd.notna(row['restroom_type']) else 'restroom',
            'multi_user_stalls': float(row['multi_user_stalls']) if pd.notna(row['multi_user_stalls']) else None,
            'has_shower': bool(row['has_shower']) if pd.notna(row['has_shower']) else False,
            'staff_only_any': bool(row['staff_only_any']) if pd.notna(row['staff_only_any']) else False,
            'notes': str(row['notes']).strip() if pd.notna(row['notes']) else None,
            'place_id': str(row['place_id']).strip() if pd.notna(row['place_id']) else None,
            'formatted_address_google': str(row['formatted_address_google']).strip() if pd.notna(row['formatted_address_google']) else None,
            'latitude_google': float(row['latitude_google']) if pd.notna(row['latitude_google']) else None,
            'longitude_google': float(row['longitude_google']) if pd.notna(row['longitude_google']) else None,
            'google_maps_url': str(row['google_maps_url']).strip() if pd.notna(row['google_maps_url']) else None,
            'google_directions_url': str(row['google_directions_url']).strip() if pd.notna(row['google_directions_url']) else None,
            'geocode_method': str(row['geocode_method']).strip() if pd.notna(row['geocode_method']) else None,
            'within_campus_bbox': bool(row['within_campus_bbox']) if pd.notna(row['within_campus_bbox']) else True,
        }
        
        restrooms_data.append(restroom_record)
    
    print(f"Prepared {len(restrooms_data)} restroom records for insertion")
    
    try:
        # Clear existing data
        print("Clearing existing restroom data...")
        supabase.table("restrooms").delete().neq('id', 0).execute()
        
        # Insert new data in batches
        batch_size = 50
        for i in range(0, len(restrooms_data), batch_size):
            batch = restrooms_data[i:i + batch_size]
            print(f"Inserting batch {i//batch_size + 1}: records {i+1} to {min(i+batch_size, len(restrooms_data))}")
            
            response = supabase.table("restrooms").insert(batch).execute()
            
            if response.data:
                print(f"Successfully inserted {len(response.data)} records")
            else:
                print(f"Warning: No data returned for batch {i//batch_size + 1}")
        
        print(f"Database population completed! Inserted {len(restrooms_data)} restroom records.")
        
    except Exception as e:
        print(f"Error populating database: {str(e)}")

if __name__ == "__main__":
    populate_restrooms_database()
