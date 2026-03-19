import os
import json
import logging
import time
import urllib.parse
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

from modules.url_sanitizer import normalize_domain_url
from modules.module_1_prospecting import run_module_1
from modules.module_2_research import run_traffic, run_backlinks, run_analysis, load_json, save_json, CACHE_FILE
from modules.module_4_outreach import run_outreach
from modules.module_6_apollo import run_apollo_enrichment

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

    # 2. Read Column A:Z to capture verdict and custom inputs
    result = sheet.values().get(spreadsheetId=sheet_id, range="Sheet1!A:Z").execute()
    rows = result.get('values', [])
    
    headers = rows[0] if rows else ["URL (Domain)"]
    existing_data = [] # tuple (url, verdict, col_s_val)
    
    idx_verdict = headers.index("Lead Qualification (Verdict)") if "Lead Qualification (Verdict)" in headers else 14
    
    for r in rows[1:]:
        if r and str(r[0]).strip():
            url = str(r[0]).strip()
            v = r[idx_verdict].strip() if len(r) > idx_verdict else None
            # Column S is index 18
            col_s_val = r[18].strip() if len(r) > 18 else ""
            existing_data.append((url, v, col_s_val))
            
    # Normalize existing URLs
    normalized_list = []
    seen = set()
    updates = []
    
    # Clean up Column A
    for i, (raw_url, v, custom_points) in enumerate(existing_data):
        row_num = i + 2
        norm = normalize_domain_url(raw_url)
        
        if norm != "INVALID_URL" and norm not in seen:
            seen.add(norm)
            normalized_list.append((row_num, norm, v, custom_points))
            if norm != raw_url:
                updates.append({"range": f"Sheet1!A{row_num}", "values": [[norm]]})
                
    # If any need normalization in sheet, update them
    if updates:
        body = {"valueInputOption": "USER_ENTERED", "data": updates}
        sheet.values().batchUpdate(spreadsheetId=sheet_id, body=body).execute()
        logging.info(f"Normalized {len(updates)} existing rows in Google Sheet towards root domains.")

    # Goal: 9 total domains to reach row 10
    current_domain_count = len(normalized_list)
    desired_domain_count = 9
    
    prospects_to_add = []
    
    # Try to add if not enough
    if current_domain_count < desired_domain_count:
        logging.info(f"Currently have {current_domain_count} domains. Prospecting for more...")
        with open('config/client_profile_template.json', 'r') as f:
            config = json.load(f)
        
        raw_prospects = run_module_1(config['search_parameters'], config['client_details']['website_url'])
        
        for p in raw_prospects:
            norm = normalize_domain_url(p.get("url", ""))
            if norm == "INVALID_URL":
                norm = normalize_domain_url(p.get("domain", ""))
                
            if norm != "INVALID_URL" and norm not in seen:
                seen.add(norm)
                prospects_to_add.append(norm)
                if len(normalized_list) + len(prospects_to_add) >= desired_domain_count:
                    break

        if prospects_to_add:
            append_body = {"values": [[p] for p in prospects_to_add]}
            sheet.values().append(
                spreadsheetId=sheet_id,
                range="Sheet1!A:A",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=append_body
            ).execute()
            
            # Re-fetch after insert
            result_new = sheet.values().get(spreadsheetId=sheet_id, range="Sheet1!A:R").execute()
            rows_new = result_new.get('values', [])
            
            normalized_list = []
            seen = set()
            for i, r in enumerate(rows_new[1:]):
                if r and str(r[0]).strip():
                    url = str(r[0]).strip()
                    v = r[idx_verdict].strip() if len(r) > idx_verdict else None
                    col_s_val = r[18].strip() if len(r) > 18 else ""
                    seen.add(url)
                    normalized_list.append((i + 2, url, v, col_s_val))
            
            logging.info(f"Successfully populated prospects.")

    # Process rows 2 to 10 strictly
    targets = []
    for r_num, url, v, custom_points in normalized_list:
        if 2 <= r_num <= 10:
            domain_only = urllib.parse.urlparse(url).netloc
            targets.append({
                "Domain": domain_only, 
                "URL (Domain)": url, 
                "_row_num": r_num, 
                "sheet_verdict": v,
                "custom_points": custom_points
            })
            
    if not targets:
        logging.info("No targets found between row 2 and 10.")
        return
        
    logging.info(f"Executing Batch Processing on {len(targets)} domains (Rows 2-10).")
    
    def normalize_output_format(p):
        geo = p.get("Phase 2 - Geography")
        if geo and isinstance(geo, str):
            if not geo.startswith("🟢") and not geo.startswith("🔴") and geo != "TBD":
                target_geos = ["US", "UK", "AU", "WW", "CA"]
                p["Phase 2 - Geography"] = f"🟢 {geo}" if any(g in geo for g in target_geos) else f"🔴 {geo}"

        spam = p.get("Phase 3 - Spam Score")
        if spam is not None and str(spam) not in ["TBD", "N/A", "None", ""]:
            try:
                p["Phase 3 - Spam Score"] = int(float(str(spam)))
            except:
                p["Phase 3 - Spam Score"] = None
        elif str(spam) in ["TBD", "N/A", "None", ""]:
            p["Phase 3 - Spam Score"] = None

        qs = p.get("Quality Score (Phase 1 & 2)")
        if qs is not None:
            if isinstance(qs, str) and "Rank:" in qs:
                p["Quality Score (Phase 1 & 2)"] = None
            else:
                try:
                    p["Quality Score (Phase 1 & 2)"] = int(qs)
                except:
                    p["Quality Score (Phase 1 & 2)"] = None
                    
        total_seo = p.get("_cost_bl", 0.0) + p.get("_cost_tr", 0.0)
        p["Total Cost (USD)"] = f"${total_seo:.5f}"
        p["Cost Breakdown"] = f"DataForSEO: ${total_seo:.5f} | Gemini: Free"
        
        signals_dict = {}
        red_flag_text = p.get("Phase 1 - Write for Us Red Flags")
        topic_text = p.get("Phase 1 - Topical Match")
        inbound_text = p.get("Phase 3 - Inbound Ratios")
        
        if red_flag_text:
            if "🔴" in red_flag_text: signals_dict["red"] = "RED"
            elif "🟢" in red_flag_text: signals_dict["red"] = "GREEN"
            
        if topic_text:
            if "🔴" in topic_text: signals_dict["top"] = "RED"
            elif "🟢" in topic_text: signals_dict["top"] = "GREEN"

        geo_val = p.get("Phase 2 - Geography")
        if geo_val:
            if "🔴" in geo_val: signals_dict["geo"] = "RED"
            elif "🟢" in geo_val: signals_dict["geo"] = "GREEN"

        if inbound_text:
            if "🔴" in inbound_text: signals_dict["inb"] = "RED"
            elif "🟢" in inbound_text: signals_dict["inb"] = "GREEN"
            
        if p.get("Phase 3 - Spam Score") is not None:
            sp = p["Phase 3 - Spam Score"]
            if sp <= 30: signals_dict["spam"] = "GREEN"
            elif sp <= 60: signals_dict["spam"] = "YELLOW"
            else: signals_dict["spam"] = "RED"
            
        signals_full = list(signals_dict.values())
        
        score = 30
        for s in signals_full:
            if s == "GREEN": score += 8
            elif s == "YELLOW": score += 3
            elif s == "RED": score -= 25
            
        present_signals = [s for s in signals_full if s is not None]
        total_signals = 5
        comp_ratio = len(present_signals) / total_signals if total_signals > 0 else 0
        if comp_ratio == 1.0: score += 5
        elif comp_ratio >= 0.6: score += 3
        elif comp_ratio < 0.4: score -= 10
        if "RED" in present_signals: score = min(score, 60)
            
        score = max(0, min(100, int(score)))
        p["score"] = score
        
        sv = p.get("sheet_verdict")
        if sv in ["🟢 APPROVED", "🟡 REVIEW", "🔴 REJECTED"]:
            p["verdict"] = sv
        elif "verdict" not in p or p["verdict"] not in ["🟢 APPROVED", "🟡 REVIEW", "🔴 REJECTED"]:
            if "RED" in present_signals:
                p["verdict"] = "🔴 REJECTED"
            elif "YELLOW" in present_signals:
                p["verdict"] = "🟡 REVIEW"
            else:
                p["verdict"] = "🟢 APPROVED"
        return p
        
    processed_targets = []
    cache_data = load_json(CACHE_FILE)
    
    for p in targets:
        d_name = p['Domain']
        cached_p = cache_data.get(d_name, {})
        p.update({k: v for k, v in cached_p.items() if k not in p or p[k] is None})
            
        if p.get("_fully_processed"):
            p = normalize_output_format(p)
            logging.info(f"⏭️ HARD SKIP Row {p['_row_num']} ({p['Domain']}) → Fully processed ({p.get('verdict')})")
            processed_targets.append(p)
            continue
            
        logging.info(f"Processing object for Row {p['_row_num']}: {p['Domain']}")
        row_start = time.time()
        
        if p.get("sheet_verdict") == "🟢 APPROVED":
            p["_traffic_done"] = True
            p["_backlinks_done"] = True
            p["_gemini_done"] = True
            p["verdict"] = "🟢 APPROVED"

        if not p.get("_traffic_done"): p = run_traffic([p])[0]
        if not p.get("_backlinks_done"): p = run_backlinks([p])[0]
        if not p.get("_gemini_done"): p = run_analysis([p])[0]
        
        row_end = time.time()
        p["time_taken"] = round(p.get("time_taken", 0) + (row_end - row_start), 2)
        p["_fully_processed"] = True
        
        if d_name not in cache_data:
            cache_data[d_name] = {}
        cache_data[d_name].update(p)
        save_json(cache_data, CACHE_FILE)
        p = normalize_output_format(p)
        processed_targets.append(p)
        
    targets = processed_targets
    
    # 3. Outreach & Enrichment
    client_profile_path = "config/client_profile_template.json"
    client_profile = {}
    if os.path.exists(client_profile_path):
        with open(client_profile_path, 'r') as f:
            client_profile = json.load(f)
            
    targets = run_outreach(targets, client_profile)
    targets = run_apollo_enrichment(targets)
    
    # 4. Final Database Write Safely (Dynamic Column Mapping)
    update_data = []

    def safe_val(v):
        if v is None: return ""
        if isinstance(v, str) and any(err in v for err in ["API Message", "TBD", "Error"]): return ""
        return str(v)

    # Ensure Subject and Body are mapped into headers dynamically if they don't exist
    header_update_needed = False
    if "Outreach Subject" not in headers:
        headers.append("Outreach Subject")
        header_update_needed = True
    if "Outreach Email Body" not in headers:
        headers.append("Outreach Email Body")
        header_update_needed = True
        
    if header_update_needed:
        sheet.values().update(spreadsheetId=sheet_id, range="Sheet1!1:1", valueInputOption="USER_ENTERED", body={"values": [headers]}).execute()
        
    col_map = {h.strip(): chr(65 + i) if i < 26 else f"A{chr(65 + (i - 26))}" for i, h in enumerate(headers)}

    for p in targets:
        row_num = p["_row_num"]
        
        spam = p.get("Phase 3 - Spam Score")
        spam_str = ""
        if spam is not None:
            if spam <= 30: spam_str = "🟢"
            elif spam <= 60: spam_str = "🟡"
            else: spam_str = "🔴"

        # Explicit mapping mapping logic guarantees we only touch EXACT columns 
        updates_dict = {
            "Phase 1 - Write for Us Red Flags": safe_val(p.get("Phase 1 - Write for Us Red Flags")),
            "Phase 1 - Topical Match": safe_val(p.get("Phase 1 - Topical Match")),
            "Quality Score (Phase 1 & 2)": safe_val(p.get("Quality Score (Phase 1 & 2)")),
            "Contact": safe_val(p.get("Contact")),
            "Phase 2 - Geography": safe_val(p.get("Phase 2 - Geography")),
            "Phase 2 - Traffic Volume": safe_val(p.get("Phase 2 - Traffic Volume")),
            "Phase 3 - Inbound Ratios": safe_val(p.get("Phase 3 - Inbound Ratios")),
            "Phase 3 - Spam Score": spam_str,
            "Time Taken (Seconds)": str(p.get("time_taken", 0)),
            "Total Cost (USD)": safe_val(p.get("Total Cost (USD)")),
            "Cost Breakdown": safe_val(p.get("Cost Breakdown")),
            "Lead Qualification (Verdict)": p.get("verdict"),
            "Score": str(p.get("score")) if p.get("score") is not None else "",
            "Outreach Subject": safe_val(p.get("Outreach Subject")),
            "Outreach Email Body": safe_val(p.get("Outreach Body"))
        }

        # Dynamically append specifically mapped cells, ignoring custom columns like First/Last Name
        for col_name, val in updates_dict.items():
            if col_name in col_map and val != "":
                col_letter = col_map[col_name]
                update_data.append({
                    "range": f"Sheet1!{col_letter}{row_num}",
                    "values": [[val]]
                })

    if update_data:
        body = {
            "valueInputOption": "USER_ENTERED",
            "data": update_data
        }
        sheet.values().batchUpdate(
            spreadsheetId=sheet_id,
            body=body
        ).execute()
        logging.info(f"Success! Exported profiles via safe dynamic column mapping to Google Sheets.")

if __name__ == "__main__":
    main()
