import os
import requests
from supabase import create_client

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Hunter.io
HUNTER_KEY = os.getenv("HUNTER_KEY")
HUNTER_URL = "https://api.hunter.io/v2/email-finder"

def enrich_email(email, domain=None):
    params = {"email": email, "domain": domain, "api_key": HUNTER_KEY}
    response = requests.get(HUNTER_URL, params=params)
    if response.status_code == 200:
        data = response.json().get("data", {})
        return {
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "position": data.get("position"),
            "company": data.get("company"),
            "verified": data.get("verification", {}).get("status"),
            "source": data.get("sources")
        }
    return {"email": email, "first_name": None, "last_name": None,
            "position": None, "company": None, "verified": None, "source": None}

# Funciones Supabase
def get_user(email):
    user = supabase.table("users").select("*").eq("email", email).execute()
    return user.data[0] if user.data else None

def update_quota(email, increment=1):
    user = get_user(email)
    if user:
        new_quota = user["quota"] - increment
        supabase.table("users").update({"quota": new_quota}).eq("email", email).execute()
        return new_quota
    return None
