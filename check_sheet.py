import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()
creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
sheet_id = os.getenv("GOOGLE_SHEET_ID")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

result = sheet.values().get(spreadsheetId=sheet_id, range="Sheet1!A1:A10").execute()
rows = result.get('values', [])
for i, row in enumerate(rows):
    print(f"Row {i+1}: {row}")
