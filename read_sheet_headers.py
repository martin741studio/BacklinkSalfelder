import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

def main():
    creds_file = "config/credentials.json"
    sheet_id = "1cX_G5JbIYeb2pWSEeIc06zHSLdOFCU2_ImUBZxZwb_E"
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    
    result = sheet.values().get(spreadsheetId=sheet_id, range="A1:Z10").execute()
    values = result.get('values', [])
    for row in values:
        print(row)

if __name__ == "__main__":
    main()
