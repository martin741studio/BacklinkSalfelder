import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

def load_dotenv_dict(filepath):
    """Load dotenv variables without python-dotenv library."""
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k.strip()] = v.strip()

load_dotenv_dict(".env")
creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
# Target spreadsheet provided by user
target_sheet_id = "17O0lrUrMguiQxIiKiy7k5_xf96PbKLZtRij00rBD2wM"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

try:
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    # Define the values to write
    values = [
        ["AI Test", "Appended row successfully"]
    ]
    body = {
        'values': values
    }

    # Append the row
    result = sheet.values().append(
        spreadsheetId=target_sheet_id,
        range="Sheet1!A:B",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    
    print(f"Successfully appended {result.get('updates').get('updatedCells')} cells.")
except Exception as e:
    print(f"Failed to append: {e}")
