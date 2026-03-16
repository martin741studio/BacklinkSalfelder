import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

def run_module_3(researched_data):
    """
    Module 3: Database Entry
    Takes enriched (or raw) prospects and pushes them cleanly into Google Sheets.
    """
    logging.info("Starting Module 3: Database Entry (Google Sheets)")
    
    # Setup credentials
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    if not os.path.exists(creds_file):
        logging.error(f"Google credentials file not found at {creds_file}")
        return
        
    if not sheet_id:
        logging.error("GOOGLE_SHEET_ID not set in .env")
        return

    # Authenticate and build service
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(
        creds_file, scopes=SCOPES)
        
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # 1. First, check if headers exist. If the sheet is completely empty, add them.
        result = sheet.values().get(spreadsheetId=sheet_id, range="Sheet1!A1:G1").execute()
        headers = result.get('values', [])
        
        expected_headers = [
            "URL (Domain)",
            "Phase 1 - Write for Us Red Flags",
            "Phase 1 - Topical Match",
            "Quality Score (Phase 1 & 2)",
            "Contact",
            "Phase 2 - Geography",
            "Phase 2 - Traffic Volume",
            "Phase 3 - Inbound Ratios",
            "Phase 3 - Spam Score",
            "Time Taken (Seconds)",
            "Total Cost (USD)",
            "Cost Breakdown"
        ]
        
        if not headers:
            logging.info("Sheet is empty, writing headers...")
            body = {'values': [expected_headers]}
            sheet.values().update(
                spreadsheetId=sheet_id, range="Sheet1!A1",
                valueInputOption="RAW", body=body).execute()

        # 2. Get existing domains to avoid duplicates
        existing_data = sheet.values().get(spreadsheetId=sheet_id, range="Sheet1!A:A").execute()
        existing_domain_urls = [row[0] for row in existing_data.get('values', []) if row]
        
        # 3. Prepare rows to append
        rows_to_append = []
        for item in researched_data:
            url_domain = item.get('URL (Domain)', 'TBD')
            if str(url_domain) in existing_domain_urls:
                continue # Skip existing domain
            p1_flags = item.get('Phase 1 - Write for Us Red Flags', 'TBD')
            p1_match = item.get('Phase 1 - Topical Match', 'TBD')
            quality = item.get('Quality Score (Phase 1 & 2)', 'TBD')
            contact = item.get('Contact', 'TBD')
            p2_geography = item.get('Phase 2 - Geography', 'TBD')
            p2_traffic = item.get('Phase 2 - Traffic Volume', 'TBD')
            p3_ratios = item.get('Phase 3 - Inbound Ratios', 'TBD')
            p3_spam = item.get('Phase 3 - Spam Score', 'TBD')
            time_taken = item.get('Time Taken (Seconds)', 'TBD')
            total_cost = item.get('Total Cost (USD)', 'N/A')
            cost_break = item.get('Cost Breakdown', 'N/A')
            
            row = [
                str(url_domain),
                str(p1_flags),
                str(p1_match),
                str(quality),
                str(contact),
                str(p2_geography),
                str(p2_traffic),
                str(p3_ratios),
                str(p3_spam),
                str(time_taken),
                str(total_cost),
                str(cost_break)
            ]
            rows_to_append.append(row)
            
        # 4. Append to sheet
        if rows_to_append:
            body = {'values': rows_to_append}
            sheet.values().append(
                spreadsheetId=sheet_id,
                range="Sheet1!A:L",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            logging.info(f"Successfully pushed {len(rows_to_append)} rows to Google Sheet.")
        else:
            logging.info("No new rows to append (all domains already exist in Google Sheet).")
            
    except Exception as e:
        logging.error(f"Failed connecting to Google Sheets: {e}")

# Local testing
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    mock_data = [{"domain": "testlaw.com", "url": "https://testlaw.com/contact", "source_query": "Test"}]
    run_module_3(mock_data)
