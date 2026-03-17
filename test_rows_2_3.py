import os
import json
import logging
import urllib.parse
import time
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

from modules.module_2_research import run_traffic, run_backlinks, run_analysis

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    load_dotenv(override=True)
    
    # 1. Google Sheets Setup
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    
    # 2. Read exactly A2 and A3
    result = sheet.values().get(spreadsheetId=sheet_id, range="Sheet1!A2:A3").execute()
    rows = result.get('values', [])
    if not rows:
        logging.info("No domains found in A2:A3.")
        return
        
    prospects = []
    for row in rows:
        if row:
            raw_url = row[0].strip()
            domain = raw_url
            if domain.startswith("http"):
                domain = urllib.parse.urlparse(domain).netloc
            domain = domain.replace("www.", "")
            prospects.append({"Domain": domain, "URL (Domain)": raw_url})

    logging.info(f"Testing these exact domains: {[p['Domain'] for p in prospects]}")
    
    # Force delete cache for these 2 domains to guarantee fresh accurate data pull for the test
    cache_file = 'data/module_2_cache.json'
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            try:
                cache = json.load(f)
            except:
                cache = {}
        for p in prospects:
            if p["Domain"] in cache:
                del cache[p["Domain"]]
                logging.info(f"Deleted {p['Domain']} from cache for a true fresh ping.")
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=4)
            
    # Run the pipeline module by module
    # Time tracking wrapper
    start_time = time.time()

    # Run the pipeline module by module
    logging.info("Executing M2 - Traffic...")
    prospects = run_traffic(prospects)
    
    logging.info("Executing M2 - Backlinks...")
    prospects = run_backlinks(prospects)
    
    logging.info("Executing M2 - Analysis (Gemini)...")
    prospects = run_analysis(prospects)

    end_time = time.time()
    time_taken = round(end_time - start_time, 2)

    # 3. Write securely back to Row 2 and Row 3 (A:M)
    for i, p in enumerate(prospects):
        row_num = i + 2
        
        # 1. Parse base metrics (No Fallback to 0. If missing, it stays None)
        tf = p.get("Phase 2 - Traffic Volume")
        spam = p.get("Phase 3 - Spam Score")

        # 2. Extract AI text
        red_flag_text = p.get("Phase 1 - Write for Us Red Flags")
        topic_text = p.get("Phase 1 - Topical Match")
        geo_text = p.get("Phase 2 - Geography")
        inbound_text = p.get("Phase 3 - Inbound Ratios")

        # 3. Process Signals for new Verdict Engine
        signals_dict = {}

        if red_flag_text:
            if "🔴" in red_flag_text: signals_dict["red_flags_status"] = "RED"
            elif "🟢" in red_flag_text: signals_dict["red_flags_status"] = "GREEN"
            
        if topic_text:
            if "🔴" in topic_text: signals_dict["topical_status"] = "RED"
            elif "🟢" in topic_text: signals_dict["topical_status"] = "GREEN"

        if geo_text:
            if "🔴" in geo_text: signals_dict["geo_status"] = "RED"
            elif "🟢" in geo_text: signals_dict["geo_status"] = "GREEN"

        if inbound_text:
            if "🔴" in inbound_text: signals_dict["inbound_status"] = "RED"
            elif "🟢" in inbound_text: signals_dict["inbound_status"] = "GREEN"

        spam_val_str = None
        if spam is not None:
            if spam <= 30:
                signals_dict["spam_status"] = "GREEN"
                spam_val_str = "🟢"
            elif spam <= 60:
                signals_dict["spam_status"] = "YELLOW"
                spam_val_str = "🟡"
            else:
                signals_dict["spam_status"] = "RED"
                spam_val_str = "🔴"
            
        # 4. User's exact mathematical GET_VERDICT engine:
        signals_full = [
            signals_dict.get("red_flags_status"),
            signals_dict.get("topical_status"),
            signals_dict.get("geo_status"),
            signals_dict.get("inbound_status"),
            signals_dict.get("spam_status")
        ]
        
        # 4.5 Confidence Score Plugin (Column N)
        score = 30
        for s in signals_full:
            if s == "GREEN": score += 8
            elif s == "YELLOW": score += 3
            elif s == "RED": score -= 25
            
        present_signals = [s for s in signals_full if s is not None]
        total_signals = 5
        comp_ratio = len(present_signals) / total_signals
        
        if comp_ratio == 1.0: score += 5
        elif comp_ratio >= 0.6: score += 3
        elif comp_ratio < 0.4: score -= 10
        
        # RED Signal Hard Cap
        if "RED" in present_signals:
            score = min(score, 60)
            
        score = max(0, min(100, score))
        
        # REMOVE missing data
        signals = present_signals

        if "RED" in signals:
            verdict = "🔴 REJECTED"
        elif "YELLOW" in signals:
            verdict = "🟡 REVIEW"
        else:
            verdict = "🟢 APPROVED"

        # Output Sanity Filter: Enforce no fallback strings
        def safe_val(v):
            if v is None: return None
            if isinstance(v, str) and any(err in v for err in ["API Message", "TBD", "Error"]): return None
            return v

        # 5. Build Final Array (Strictly B thru N)
        values = [
            safe_val(red_flag_text), # B
            safe_val(topic_text), # C
            safe_val(p.get("Quality Score (Phase 1 & 2)")), # D
            safe_val(p.get("Contact")), # E
            safe_val(geo_text), # F
            safe_val(tf), # G
            safe_val(inbound_text), # H
            safe_val(spam_val_str), # I
            time_taken, # J
            safe_val(p.get("Total Cost (USD)")), # K
            safe_val(p.get("Cost Breakdown")), # L
            verdict, # M
            score # N
        ]

        logging.info(f"Row {row_num} Payload: {values}")

        sheet.values().update(
            spreadsheetId=sheet_id,
            range=f"Sheet1!B{row_num}:N{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": [values]}
        ).execute()
        logging.info(f"Successfully injected fully-populated columns into Row {row_num}")
        
if __name__ == "__main__":
    main()
