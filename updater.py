import requests
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# --- CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
LEAGUE_ID = 1  # World Cup 2026 ID (To be confirmed when API updates)
SEASON = 2026

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def sync_live_scores():
    print(f"[{datetime.now()}] Starting Sync...")
    
    url = f"https://v3.football.api-sports.io/fixtures?league={LEAGUE_ID}&season={SEASON}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    
    try:
        response = requests.get(url, headers=headers).json()
        fixtures = response.get('response', [])
        
        for f in fixtures:
            fixture_id = f['fixture']['id']
            home_score = f['goals']['home']
            away_score = f['goals']['away']
            status = f['fixture']['status']['short'] # 'FT' = Finished, '1H', '2H' = Live
            
            # 1. Update the Match Score
            # 2. If status is 'FT', the Database Trigger in Supabase 
            #    will AUTOMATICALLY calculate everyone's points instantly!
            
            db_status = 'finished' if status == 'FT' else 'live' if status in ['1H', '2H', 'HT', 'ET', 'P'] else 'scheduled'
            
            supabase.table("matches").upsert({
                "api_fixture_id": fixture_id,
                "home_score": home_score,
                "away_score": away_score,
                "status": db_status,
                "home_team": f['teams']['home']['name'],
                "away_team": f['teams']['away']['name'],
                "kickoff_time": f['fixture']['date']
            }, on_conflict="api_fixture_id").execute()
            
        print(f"Successfully synced {len(fixtures)} matches.")
        
    except Exception as e:
        print(f"Sync failed: {e}")

if __name__ == "__main__":
    sync_live_scores()
