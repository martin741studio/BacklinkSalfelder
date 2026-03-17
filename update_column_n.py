import os
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_headers():
    load_dotenv(override=True)
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    
    sheet_metadata = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheets = sheet_metadata.get('sheets', '')
    sheet_id_num = None
    for s in sheets:
        if s.get("properties", {}).get("title", "") == "Sheet1":
            sheet_id_num = s.get("properties", {}).get("sheetId", 0)
            break
            
    if sheet_id_num is None:
        sheet_id_num = 0

    requests = []
    
    # Update Column N (Index 13) Header Value
    requests.append({
        "updateCells": {
            "range": {
                "sheetId": sheet_id_num,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 13,
                "endColumnIndex": 14
            },
            "rows": [
                {
                    "values": [
                        {
                            "userEnteredValue": {"stringValue": "Confidence Score (0-100)"},
                            "note": "Confidence Score (0-100)\nReflects how reliable the verdict is based on data completeness, signal strength, and consistency. Score ranges from 0-100."
                        }
                    ]
                }
            ],
            "fields": "userEnteredValue,note"
        }
    })
        
    body = {
        'requests': requests
    }
    
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body=body
    ).execute()
    logging.info("Successfully updated Column N header value and note.")

if __name__ == "__main__":
    update_headers()
