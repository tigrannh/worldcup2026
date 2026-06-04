import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

# --- CONFIG ---
API_KEY = os.environ.get("API_FOOTBALL_KEY")
URL = "https://v3.football.api-sports.io/fixtures"
HEADERS = {"x-apisports-key": API_KEY}

def test_single_match():
    # Test with 2022 World Cup Final (Argentina vs France) to see a real finished match JSON
    # League 1 (World Cup), Season 2022, ID for the Final was 855734
    params = {"id": 855734} 
    
    print("🚀 CALLING API FOR TEST MATCH (2022 FINAL)...")
    response = requests.get(URL, headers=HEADERS, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ RAW JSON RETURNED FROM API:")
        print(json.dumps(data, indent=2))
        
        # Explain the "Robot Logic"
        res = data['response'][0]
        home = res['teams']['home']['name']
        away = res['teams']['away']['name']
        status = res['fixture']['status']['short']
        h_score = res['goals']['home']
        a_score = res['goals']['away']
        
        print("\n--- ROBOT INTERPRETATION ---")
        print(f"Match: {home} vs {away}")
        print(f"Status: {status} (FT = Finished)")
        print(f"Final Score: {h_score} - {a_score}")
        print("----------------------------")
    else:
        print(f"❌ API Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_single_match()
