import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from modules.module_0_client_research import run_client_research

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_env():
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(env_path)

def main():
    load_env()

    sheet_id = "1cX_G5JbIYeb2pWSEeIc06zHSLdOFCU2_ImUBZxZwb_E"
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds_path = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
    try:
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    except FileNotFoundError:
        logging.error(f"Could not find credentials file at {creds_path}.")
        return
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    
    # Read everything
    result = sheet.values().get(spreadsheetId=sheet_id, range="A:B").execute()
    values = result.get('values', [])
    
    if not values:
        logging.error("Sheet is empty.")
        return
        
    import re
    row_map = {}
    current_section = 0
    
    for i, row in enumerate(values):
        if not row: continue
        raw_label = str(row[0]).strip()
        
        # Check for section number
        match = re.search(r"^(\d+)\.", raw_label)
        if match:
            current_section = int(match.group(1))
            
        # Clean label for keying
        label = raw_label.replace("•", "").strip()
        
        if not label: continue
        
        # Static sections that we DO NOT MODIFY or SEND (Rule: STATIC FIELDS (DO NOT MODIFY))
        if current_section in [3, 7, 8, 9, 10]:
            continue
            
        # Ignore actual headers / section titles to save tokens
        if re.match(r"^(\d+)\.", label) or label.isupper() or label.endswith(":"):
            continue
            
        if "domain" in label.lower() or "google business" in label.lower() or "unternehmen in der" in label.lower():
            if "unternehmen in der nähe" not in label.lower() and "ergänzende dien" not in label.lower():
                # Allow sub-bullets in section 4, but block the generic domain/gbp fields from being regenerated
                if "domain" in label.lower() and current_section == 1:
                    continue
                if "google business" in label.lower() and current_section == 1:
                    continue

        # Skip manual SEO tracking fields
        if label.lower() in ["domain rating (dr)", "monatlicher traffic", "backlinks"]:
            continue

        # Treat as dynamic or conditional field
        current_val = str(row[1]).strip() if len(row) > 1 else ""
        row_map[label] = {
            "index": i,  # 0-indexed sheet row (actual sheet row = i + 1)
            "value": current_val,
            "section": current_section
        }
        
    logging.info(f"Targeting {len(row_map)} dynamic/conditional fields from the sheet.")
    
    domain_val = ""
    gbp_val = ""
    for r in values:
        if not r: continue
        lbl = str(r[0]).lower()
        if lbl == "domain":
            domain_val = str(r[1]).strip() if len(r) > 1 else ""
        elif "google business" in lbl:
            gbp_val = str(r[1]).strip() if len(r) > 1 else ""
    
    if not domain_val:
        logging.warning("Domain is empty. Cannot perform research.")
        return
        
    logging.info(f"Starting research for {domain_val} / GBP {gbp_val}")
    os.environ["GEMINI_API_KEY"] = "AIzaSyBZKObgdZdIQhp7wtSKrBhzqmgLO22EbGs"
    
    # We want Gemini to fill everything, so let's pass all the relevant labels
    fields_target = {label: details["value"] for label, details in row_map.items()}

    result_data = run_client_research(domain_val, gbp_val, fields_dict=fields_target)
    
    if not result_data:
        logging.error("No data returned from Gemini.")
        return
        
    logging.info("Writing results to Google Sheets...")
    
    updates = []
    # result_data should have keys matching our sheet labels
    for sheet_label in row_map.keys():
        if sheet_label in result_data:
            val = result_data[sheet_label]
            if val and str(val).lower() != "not found": 
                sheet_row_num = row_map[sheet_label]["index"] + 1
                val_str = str(val)[:4000] if not isinstance(val, (list, dict)) else json.dumps(val, ensure_ascii=False)
                
                # Write to Column C for Section 4 (Zielpartner-Definition)
                col_letter = "C" if row_map[sheet_label]["section"] == 4 else "B"
                
                updates.append({
                    "range": f"{col_letter}{sheet_row_num}",
                    "values": [[val_str]]
                })

    if updates:
        body = {
            "valueInputOption": "USER_ENTERED",
            "data": updates
        }
        sheet.values().batchUpdate(
            spreadsheetId=sheet_id,
            body=body
        ).execute()
        logging.info(f"Successfully updated fields: {[u['range'] for u in updates]}")
    else:
        logging.info("No empty fields to update or no valid data found.")

if __name__ == "__main__":
    main()
