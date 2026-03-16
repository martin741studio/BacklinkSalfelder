import os
import json
import base64
import time
import requests
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

url_to_test = "https://www.udara-bali.com/"
domain_to_test = "udara-bali.com"

results = {
    "Domain": domain_to_test,
    "URL": url_to_test,
    
    # Phase 1
    "Phase 1 - Real Website vs PBN": "TBD",
    "Phase 1 - Topical Match": "TBD",
    "Phase 1 - Content Quality": "TBD",
    "Phase 1 - Write for Us Red Flags": "TBD",
    "Phase 1 - Contactability": "TBD",

    # Phase 2
    "Phase 2 - Domain Rank": "TBD",
    "Phase 2 - Traffic Volume": "TBD",
    "Phase 2 - Geography": "TBD",

    # Phase 3
    "Phase 3 - Inbound Ratios": "TBD",
    "Phase 3 - Spam Score": "TBD",
    
    "Time Taken (Seconds)": 0
}

start_time = time.time()

# 1. Scrape the website
print("Scraping website...")
try:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url_to_test, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    text_content = soup.get_text(separator=' ', strip=True)
    clean_text = ' '.join(text_content.split())[:3000] # Take first 3000 chars

    # Extract emails
    emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', response.text))
    
    # Filter out noisy emails (png, jpg extensions)
    valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))]
    results["Phase 1 - Contactability"] = ", ".join(valid_emails) if valid_emails else "None Found"
except Exception as e:
    clean_text = ""
    results["Phase 1 - Contactability"] = f"Error: {e}"

# 2. Gemini Analysis
print("Running Gemini AI Check...")
api_key = os.getenv("GEMINI_API_KEY")
if api_key and clean_text:
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        Analyze this website text from a wellness center in Canggu Bali.
        Text: {clean_text}
        
        Answer these 4 questions briefly (1 sentence each):
        1. Real Website vs PBN? Does it seem like a genuine business?
        2. Topical match? Does it focus on wellness, spa, recovery, yoga?
        3. Content quality? Is it professionally written?
        4. "Write for Us" Red Flags? Does it beg for guest posts or ads?
        
        Format as JSON with exact keys: 'real_website', 'topical_match', 'content_quality', 'red_flags'.
        """
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        # Parse JSON safely
        resp_text = resp.text
        if "```json" in resp_text:
             resp_text = resp_text.split("```json")[1].split("```")[0].strip()
        ans = json.loads(resp_text)
        results["Phase 1 - Real Website vs PBN"] = ans.get("real_website", "Parse error")
        results["Phase 1 - Topical Match"] = ans.get("topical_match", "Parse error")
        results["Phase 1 - Content Quality"] = ans.get("content_quality", "Parse error")
        results["Phase 1 - Write for Us Red Flags"] = ans.get("red_flags", "Parse error")
    except Exception as e:
         print(f"Gemini API Error: {e}")
         results["Phase 1 - Real Website vs PBN"] = f"Error: {e}"

# 3. DataForSEO APIs
print("Getting DataForSEO Metrics...")
login = os.getenv("DATAFORSEO_LOGIN")
password = os.getenv("DATAFORSEO_PASSWORD")
credentials = f"{login}:{password}"
base64_bytes = base64.b64encode(credentials.encode("ascii")).decode("ascii")

total_seo_cost = 0
cost_bl = 0
cost_tr = 0

# A) Backlinks Summary
try:
    url_bl = "https://api.dataforseo.com/v3/backlinks/summary/live"
    post_data = [{"target": domain_to_test}]
    req = requests.post(url_bl, json=post_data, headers={"Authorization": f"Basic {base64_bytes}"})
    data = req.json()
    cost_bl = data.get("cost", 0)
    total_seo_cost += cost_bl
    if data.get("tasks") and data["tasks"][0].get("result") and len(data["tasks"][0]["result"]) > 0:
        res = data["tasks"][0]["result"][0]
        results["Phase 2 - Domain Rank"] = res.get("rank", "N/A")
        rd = res.get("referring_domains", 0)
        bl = res.get("backlinks", 1)
        results["Phase 3 - Inbound Ratios"] = f"{rd} RD / {bl} BL"
        results["Phase 3 - Spam Score"] = res.get("backlinks_spam_score", "N/A")
        
        countries = res.get("referring_links_countries", {})
        top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:3]
        results["Phase 2 - Geography"] = ", ".join([f"{c[0]} ({c[1]})" for c in top_countries if c[0]])
except Exception as e:
    print(f"DataForSEO Backlinks Error: {e}")

# B) Traffic Volume (DataForSEO Labs API)
try:
    url_tr = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live"
    # Testing Australia (2036) since they had a lot of AU inbound links
    post_data_tr = [{"target": domain_to_test, "location_code": 2036, "language_code": "en"}]
    req_tr = requests.post(url_tr, json=post_data_tr, headers={"Authorization": f"Basic {base64_bytes}"})
    data_tr = req_tr.json()
    cost_tr = data_tr.get("cost", 0)
    total_seo_cost += cost_tr
    print("DataForSEO Traffic RESPONSE keys:", data_tr.keys())
    
    if data_tr.get("tasks") and len(data_tr["tasks"]) > 0:
        task = data_tr["tasks"][0]
        if task.get("result") and len(task["result"]) > 0:
             tr_res = task["result"][0].get("metrics", {}).get("organic", {})
             results["Phase 2 - Traffic Volume"] = tr_res.get("etv", "No Data")
             print("Traffic Result:", tr_res)
        else:
             print("Traffic Task Status:", task.get("status_message"), task.get("status_code"))
             results["Phase 2 - Traffic Volume"] = f"API Message: {task.get('status_message')}"
except Exception as e:
    print(f"DataForSEO Traffic Error: {e}")

# End Timer
end_time = time.time()
results["Time Taken (Seconds)"] = round(end_time - start_time, 2)
results["Total Cost (USD)"] = f"${total_seo_cost:.5f}"
results["Cost Breakdown"] = f"DataForSEO Backlinks: ${cost_bl:.5f} | DataForSEO Traffic: ${cost_tr:.5f} | Gemini: Unknown/Free"

import pprint
print("\n--- FINAL TRIAL EXTRACTION RESULTS ---\n")
pprint.pprint(results)

# 4. Push to Google Sheets
print("\nPusing data to Google Sheet...")
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)

    headers = [
        "URL (Domain)",                     # A
        "Phase 1 - Write for Us Red Flags", # B
        "Phase 1 - Topical Match",          # C
        "Quality Score (Phase 1 & 2)",      # D
        "Contact",                          # E
        "Phase 2 - Geography",              # F
        "Phase 2 - Traffic Volume",         # G
        "Phase 3 - Inbound Ratios",         # H
        "Phase 3 - Spam Score",             # I
        "Time Taken (Seconds)",             # J
        "Total Cost (USD)",                 # K
        "Cost Breakdown"                    # L
    ]
    
    # Construct "Quality Score" artificially for the trial display (combining Rank + PBN + Content Quality)
    quality_score = f"Rank: {results.get('Phase 2 - Domain Rank', 'N/A')} | {results.get('Phase 1 - Real Website vs PBN', '')} | {results.get('Phase 1 - Content Quality', '')}"
    
    row_data = [
        str(results.get("URL", "")),                            # A
        str(results.get("Phase 1 - Write for Us Red Flags", "")), # B
        str(results.get("Phase 1 - Topical Match", "")),        # C
        quality_score,                                          # D
        str(results.get("Phase 1 - Contactability", "")),       # E
        str(results.get("Phase 2 - Geography", "")),            # F
        str(results.get("Phase 2 - Traffic Volume", "")),       # G
        str(results.get("Phase 3 - Inbound Ratios", "")),       # H
        str(results.get("Phase 3 - Spam Score", "")),           # I
        str(results.get("Time Taken (Seconds)", "")),           # J
        str(results.get("Total Cost (USD)", "")),               # K
        str(results.get("Cost Breakdown", ""))                  # L
    ]
    
    # Write Headers if needed (we'll just append headers + data for this trial to a new space or bottom)
    append_body = {
        "values": [headers, row_data]
    }
    
    request = service.spreadsheets().values().append(
        spreadsheetId=sheet_id, 
        range="Sheet1!A1", 
        valueInputOption="USER_ENTERED", 
        insertDataOption="INSERT_ROWS", 
        body=append_body
    )
    request.execute()
    print("✅ Successfully added trial row to Google Sheet!")
except Exception as e:
    print(f"❌ Failed to push to Google Sheet: {e}")
