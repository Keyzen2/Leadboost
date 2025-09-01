import os
import requests
from supabase import create_client
import pandas as pd

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLEARBIT_KEY = os.getenv("CLEARBIT_KEY")
INVITE_CODE = os.getenv("INVITE_CODE")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
CLEARBIT_URL = "https://person.clearbit.com/v2/people/find?email={email}"

# --- Clearbit ---
def enrich_email(email):
    headers = {"Authorization": f"Bearer {CLEARBIT_KEY}"}
    response = requests.get(CLEARBIT_URL.format(email=email), headers=headers)
    if response.status_code == 200:
        data = response.json()
        return {
            "name": data.get("name", {}).get("fullName"),
            "company": data.get("employment", {}).get("name"),
            "title": data.get("employment", {}).get("title"),
            "linkedin": data.get("linkedin", {}).get("handle"),
        }
    return {"name": None, "company": None, "title": None, "linkedin": None}

# --- Supabase ---
def save_lead(record):
    supabase.table("leads").insert(record).execute()

def load_leads():
    data = supabase.table("leads").select("*").execute()
    return pd.DataFrame(data.data)

def get_user(email):
    res = supabase.table("users").select("*").eq("email", email).execute()
    return res.data[0] if res.data else None

def create_user(email, role="basic", plan="Freemium", quota=50):
    supabase.table("users").insert({
        "email": email,
        "role": role,
        "plan": plan,
        "monthly_quota": quota,
        "used_quota": 0
    }).execute()

def update_plan(email, plan):
    quota = 500 if plan.lower() == "premium" else 50
    supabase.table("users").update({"plan": plan, "role": plan.lower(), "monthly_quota": quota}).eq("email", email).execute()

def increment_quota(email, count=1):
    user = get_user(email)
    if user:
        supabase.table("users").update({"used_quota": user['used_quota'] + count}).eq("email", email).execute()
