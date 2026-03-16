import os
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clear_sheet():
    load_dotenv()
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(
        creds_file, scopes=SCOPES)
        
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # Clear everything from row 1 to perfectly reset the sheet
        sheet.values().clear(spreadsheetId=sheet_id, range="Sheet1!A1:Z").execute()
        logging.info("Google Sheet wiped completely (headers will be reconstructed).")
    except Exception as e:
        logging.error(f"Error clearing sheet: {e}")

if __name__ == "__main__":
    clear_sheet()
