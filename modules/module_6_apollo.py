import os
import json
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

CACHE_FILE = "data/module_6_apollo_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def run_apollo_enrichment(targets):
    """
    Module 6 (Apollo Enrichment Phase)
    Enriches ONLY high-quality, pre-qualified leads with email contacts.
    """
    logging.info("--- RUNNING APOLLO ENRICHMENT ---")
    
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        logging.warning("APOLLO_API_KEY not found in environment. Skipping Apollo enrichment.")
        return targets

    cache = load_cache()
    
    # Fail-safe aggregate domains
    blocked_domains = ["tripadvisor.com", "yelp.com", "booking.com", "klook.com", "agoda.com", "airbnb.com", "facebook.com", "instagram.com", "youtube.com", "medium.com"]
    valid_roles = ["founder", "owner", "marketing", "manager", "ceo", "director", "head"]

    for p in targets:
        domain = p.get("Domain", "")
        verdict = p.get("verdict", "")
        
        # Maps pipeline 'Contact' mapping which aligns to Column E
        existing_email = p.get("Contact", "").strip() 
        if not existing_email and p.get("Email"):
            existing_email = p.get("Email", "").strip()

        # Resets Tracking
        p["_apollo_attempted"] = False
        p["_apollo_enriched"] = False
        
        # 1. Skip Conditions (Strictly Enforced)
        if "APPROVED" not in verdict:
            logging.info(f"Skipping Apollo for {domain} -> Verdict is not APPROVED ({verdict})")
            continue
            
        if any(b in domain.lower() for b in blocked_domains):
            logging.info(f"Skipping Apollo for {domain} -> Blocked aggregator domain")
            continue
            
        if existing_email:
            logging.info(f"Skipping Apollo for {domain} -> Email already exists in Column E ({existing_email})")
            continue
            
        # 2. Cache Verification (Zero Waste rule)
        if domain in cache:
            logging.info(f"   -> Loaded Apollo data from cache for {domain}")
            cached_data = cache[domain]
            if cached_data.get("email"):
                found_email = cached_data["email"]
                # Even if we skipped hitting Apollo, we can safely append if valid
                if existing_email:
                    if found_email not in existing_email:
                        p["Contact"] = f"{existing_email}, {found_email}"
                else:
                    p["Contact"] = found_email
                    
                p["Email"] = p["Contact"] # mirror
                p["_apollo_enriched"] = True
            continue

        # 3. Apollo REST Execution
        logging.info(f"   -> Pinging Apollo API for highly qualified target: {domain}...")
        p["_apollo_attempted"] = True
        
        url = "https://api.apollo.io/v1/mixed_people/search"
        headers = {
            "Cache-Control": "no-cache",
            "Content-Type": "application/json" # explicitly json
        }
        
        payload = {
            "api_key": api_key,
            "q_organization_domains": [domain],
            "page": 1
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            people = data.get("people", [])
            found_email = None
            
            # Email Selection Logic (Evaluate against roles)
            for person in people:
                email = person.get("email")
                title = person.get("title", "")
                
                # Guard rails for generic empty titles
                if not title:
                    title = ""
                title = title.lower()
                
                if email and any(role in title for role in valid_roles):
                    found_email = email
                    logging.info(f"      -> Success! Found validated decision-maker email: {found_email} ({title})")
                    break
                    
            if found_email:
                if existing_email:
                    if found_email not in existing_email:
                        p["Contact"] = f"{existing_email}, {found_email}"
                else:
                    p["Contact"] = found_email
                    
                p["Email"] = p["Contact"]
                p["_apollo_enriched"] = True
                cache[domain] = {"email": found_email, "status": "success"}
                
            else:
                p["_apollo_enriched"] = False
                cache[domain] = {"email": None, "status": "no_email_found"}
                logging.info(f"      -> Apollo returned no valid decision-makers/emails for {domain}")
                
            save_cache(cache)
            time.sleep(1.5) # Soft delay for rate limits
            
        except requests.exceptions.RequestException as e:
            logging.error(f"      -> Error calling Apollo API for {domain}: {e}")
            cache[domain] = {"email": None, "status": "error"}
            save_cache(cache)
            time.sleep(1.5)
            continue
            
    return targets
