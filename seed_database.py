import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import bcrypt

# Load environment
load_dotenv()
url = os.environ.get("SUPABASE_URL")
# USE SERVICE ROLE KEY FOR SEEDING
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

def seed_users():
    # Load the generated credentials
    df = pd.read_csv('ameria_credentials.csv')
    
    users_to_insert = []
    for _, row in df.iterrows():
        # Hash the password for security
        password_bytes = row['Password'].encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
        
        users_to_insert.append({
            "username": row['Name'],
            "email": row['Email'],
            "password_hash": hashed,
            "total_points": 0,
            "jokers_remaining": 5
        })
    
    # Bulk insert into Supabase
    try:
        response = supabase.table("users").upsert(users_to_insert).execute()
        print(f"Successfully seeded {len(users_to_insert)} users into Supabase.")
    except Exception as e:
        print(f"Error seeding users: {e}")

if __name__ == "__main__":
    seed_users()
