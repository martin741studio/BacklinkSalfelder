import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests
import json
import time

def col_num_to_letter(n):
    string = ""
    while n >= 0:
        string = chr(n % 26 + 65) + string
        n = n // 26 - 1
    return string

def run_module_7():
    """
    Module 7: Smartlead Push
    Pushes approved and enriched leads from Google Sheets into Smartlead campaigns.
    """
    logging.info("Starting Module 7: Smartlead Push")
    
    # 1. Setup credentials and load env
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    sl_api_key = os.getenv("SMARTLEAD_API_KEY")
    
    if not sl_api_key:
        logging.error("No SMARTLEAD_API_KEY found.")
        return
        
    if not os.path.exists(creds_file) or not sheet_id:
        logging.error("Google credentials or Sheet ID missing.")
        return

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    
    # 2. Pull all data
    result = sheet.values().get(spreadsheetId=sheet_id, range="Sheet1!A:Z").execute()
    data = result.get('values', [])
    if not data:
        logging.info("Sheet is completely empty.")
        return
        
    headers = data[0]
    
    # 3. Ensure required control columns exist
    required_cols = ["send_status", "smartlead_campaign_id", "error_note"]
    header_updated = False
    for col in required_cols:
        if col not in headers:
            headers.append(col)
            header_updated = True
            
    if header_updated:
        body = {'values': [headers]}
        sheet.values().update(
            spreadsheetId=sheet_id, range="Sheet1!A1",
            valueInputOption="RAW", body=body).execute()
        logging.info("Added new control columns to Sheet1.")
        
    # Create an index map
    idx = {h: i for i, h in enumerate(headers)}
    
    # Check what columns exist for body and subject (handling small naming variations)
    subj_col = "Outreach Subject" if "Outreach Subject" in headers else ""
    body_col = "Outreach Email Body" if "Outreach Email Body" in headers else "Outreach Body"
    
    # 4. Agent Decision Logic & Limits
    push_limit = 50
    pushed_count = 0
    row_updates = []
    
    for row_num, row in enumerate(data[1:], start=2): # +2 for 1-based index and skipping header
        # Pad row to match headers length
        while len(row) < len(headers):
            row.append("")
            
        verdict = row[idx.get("Lead Qualification (Verdict)", -1)] if idx.get("Lead Qualification (Verdict)", -1) != -1 else ""
        contact = row[idx.get("Contact", -1)] if idx.get("Contact", -1) != -1 else ""
        first_name = row[idx.get("First Name", -1)] if idx.get("First Name", -1) != -1 else ""
        
        subject = row[idx.get(subj_col, -1)] if subj_col and idx.get(subj_col, -1) != -1 else ""
        body_text = row[idx.get(body_col, -1)] if body_col and idx.get(body_col, -1) != -1 else ""
        
        send_status = row[idx.get("send_status", -1)] if idx.get("send_status", -1) != -1 else ""
        camp_id = row[idx.get("smartlead_campaign_id", -1)] if idx.get("smartlead_campaign_id", -1) != -1 else ""
        
        # LOGIC 1: Is Lead Qualification = 🟢 APPROVED?
        if "APPROVED" not in verdict:
            continue
            
        # LOGIC 2: Does Contact (email) exist?
        if not contact or contact.lower() in ["none found", "n/a", ""]:
            continue
            
        # LOGIC 3: Is Outreach Subject + Body filled?
        if not subject or not body_text:
            continue
            
        # LOGIC 4: Is send_status empty?
        if str(send_status).strip() != "":
            continue
            
        # LOGIC 5: Is smartlead_campaign_id defined?
        if not camp_id or str(camp_id).strip() == "":
            logging.error(f"Row {row_num} (URL: {row[0]}): Missing smartlead_campaign_id. Stopping push for this lead.")
            # Critical failure -> we flag this lead that it lacks campaign mapping
            row_updates.append({"row_num": row_num, "status": "error", "note": "Missing smartlead_campaign_id"})
            continue
            
        # Limit control
        if pushed_count >= push_limit:
            logging.info(f"Reached daily push limit of {push_limit}. Stopping further pushes.")
            break
            
        # ALL TRUE -> PUSH TO SMARTLEAD payload mapping
        payload = {
            "leadList": [
                {
                    "email": contact.strip(),
                    "first_name": first_name.strip(),
                    "custom_fields": {
                        "subject": subject.strip(),
                        "body": body_text.strip()
                    }
                }
            ]
        }
        
        sl_url = f"https://server.smartlead.ai/api/v1/campaigns/{camp_id.strip()}/leads?api_key={sl_api_key}"
        try:
            res = requests.post(sl_url, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                # API success
                row_updates.append({"row_num": row_num, "status": "queued", "note": ""})
                pushed_count += 1
                logging.info(f"Pushed lead {contact} to Smartlead campaign {camp_id}.")
            else:
                # API fail
                error_msg = res.text[:200]
                row_updates.append({"row_num": row_num, "status": "error", "note": f"API Error {res.status_code}: {error_msg}"})
                logging.error(f"Failed to push {contact}. Error: {res.status_code}")
        except Exception as e:
            row_updates.append({"row_num": row_num, "status": "error", "note": f"Exception: {str(e)}"[:150]})
            logging.error(f"Error pushing {contact}: {e}")
            
        time.sleep(1) # Prevent API rate limits
        
    # 5. Update Sheet with status and errors
    if row_updates:
        data_to_update = []
        status_col_letter = col_num_to_letter(idx["send_status"])
        note_col_letter = col_num_to_letter(idx["error_note"])
        
        for update in row_updates:
            rn = update["row_num"]
            data_to_update.append({
                "range": f"Sheet1!{status_col_letter}{rn}",
                "values": [[update["status"]]]
            })
            data_to_update.append({
                "range": f"Sheet1!{note_col_letter}{rn}",
                "values": [[update["note"]]]
            })
            
        body = {
            "valueInputOption": "USER_ENTERED",
            "data": data_to_update
        }
        
        try:
            sheet.values().batchUpdate(spreadsheetId=sheet_id, body=body).execute()
            logging.info(f"Successfully updated Google Sheet with {len(row_updates)} row updates.")
        except Exception as e:
            logging.error(f"Failed to annotate Google Sheet with status: {e}")
    else:
        logging.info("No leads met criteria or no pending leads to push.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    run_module_7()
