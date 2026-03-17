import os
import json
import logging
import urllib.parse
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

from modules.module_5_reporting import run_reporting

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    load_dotenv(override=True)
    
    # 1. Google Sheets Setup
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    if not creds_file or not os.path.exists(creds_file):
        logging.error("Google credentials missing. Cannot fetch live verdicts.")
        return
        
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    logging.info("Pulling latest Pipeline State from Google Sheets...")
    
    # Read the master sheet to get the final actual verdicts
    result = sheet.values().get(spreadsheetId=sheet_id, range="Sheet1!A4:M100").execute()
    rows = result.get('values', [])
    
    # Load exact API Cost cache for financial accurate tracking
    cache_data = {}
    if os.path.exists("data/module_2_cache.json"):
        with open("data/module_2_cache.json", "r") as f:
            cache_data = json.load(f)

    targets = []
    
    for r in rows:
        if not r or not r[0].strip():
            continue
            
        url = r[0].strip()
        domain = urllib.parse.urlparse(url).netloc
        if not domain:
            domain = url # fallback if no protocol
            
        # Parse final sheet data
        verdict = r[12].strip() if len(r) > 12 else "🔴 REJECTED"
        time_taken = float(r[9]) if len(r) > 9 and r[9].strip().replace('.', '', 1).isdigit() else 0.0
        
        # Link accurate traffic, spam, and float costs back from the local Cache file
        cached_obj = cache_data.get(domain, {})
        
        obj = {
            "Domain": domain,
            "verdict": verdict,
            "time_taken": time_taken,
            "_cost_bl": cached_obj.get("_cost_bl", 0.0),
            "_cost_tr": cached_obj.get("_cost_tr", 0.0),
            "Phase 2 - Traffic Volume": cached_obj.get("Phase 2 - Traffic Volume", 0),
            "Phase 3 - Spam Score": cached_obj.get("Phase 3 - Spam Score", 0)
        }
        
        targets.append(obj)
        
    if not targets:
        logging.warning("No targets loaded from Google Sheet to evaluate. Aborting report.")
        return
        
    # Execute the audit generator
    run_reporting(targets)

if __name__ == "__main__":
    main()
