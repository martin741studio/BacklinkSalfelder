import os
import json
import logging
from .module_1_prospecting import run_module_1
from .module_3_database import run_module_3
from bs4 import BeautifulSoup
import re
import base64
import requests
from google import genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}

def save_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

import time

def run_module_2(prospects_data):
    """
    Module 2: Link Opportunity Research
    Scrape domains, ping Gemini, and fetch DataForSEO metrics.
    Caches all results to disk so we NEVER re-ping the same domain if it failed or was already checked.
    """
    logging.info("Starting Module 2: Link Opportunity Research")
    
    cache_file = 'data/module_2_cache.json'
    cached_data = load_json(cache_file)
    
    # Credentials setup
    api_key_gemini = os.getenv("GEMINI_API_KEY")
    login_seo = os.getenv("DATAFORSEO_LOGIN")
    password_seo = os.getenv("DATAFORSEO_PASSWORD")
    creds_seo = f"{login_seo}:{password_seo}"
    base64_seo = base64.b64encode(creds_seo.encode("ascii")).decode("ascii")
    
    enriched_prospects = []
    
    for i, prospect in enumerate(prospects_data):
        domain = prospect.get('domain')
        url = prospect.get('url')
        
        # 1. CHECK CACHE FIRST (Never spend tokens twice)
        if domain in cached_data:
            logging.info(f"[{i+1}/{len(prospects_data)}] Loading {domain} from CACHE (No API tokens spent).")
            enriched_prospects.append(cached_data[domain])
            continue
            
        logging.info(f"[{i+1}/{len(prospects_data)}] Analyzing NEW domain: {domain}")
        start_time = time.time()
        
        # We build the enriched object based on exactly the headers Module 3 expects
        enriched = cached_data.get(domain, {
            "Domain": domain,
            "URL (Domain)": url,
            "Phase 1 - Real Website vs PBN": "TBD",
            "Phase 1 - Topical Match": "TBD",
            "Phase 1 - Content Quality": "TBD",
            "Phase 1 - Write for Us Red Flags": "TBD",
            "Contact": "None Found",
            "Quality Score (Phase 1 & 2)": "TBD",
            "Phase 2 - Geography": "TBD",
            "Phase 2 - Traffic Volume": "TBD",
            "Phase 3 - Inbound Ratios": "TBD",
            "Phase 3 - Spam Score": "TBD",
            "Time Taken (Seconds)": 0,
            "Total Cost (USD)": "$0.00000",
            "Cost Breakdown": "DataForSEO Backlinks: $0.00 | DataForSEO Traffic: $0.00 | Gemini: Free",
            "_p2_rank": "N/A",
            "_cost_bl": 0.0,
            "_cost_tr": 0.0
        })

        # 2. BeautifulSoup Scrape (Free - Contacts & Text)
        clean_text = ""
        # Only scrape if we are missing Gemini data or Contact data
        if enriched["Phase 1 - Real Website vs PBN"] == "TBD" or enriched["Contact"] == "None Found":
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                res = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                clean_text = ' '.join(soup.get_text(separator=' ', strip=True).split())[:3000]
                
                emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', res.text))
                valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))]
                if valid_emails:
                    enriched["Contact"] = ", ".join(valid_emails)
            except Exception:
                pass 
            
        # 3. Gemini Check (Tokens)
        if api_key_gemini and clean_text and enriched["Phase 1 - Real Website vs PBN"] == "TBD":
            try:
                logging.info(f"   -> Pinging Gemini for {domain}")
                client = genai.Client(api_key=api_key_gemini)
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
                resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                resp_text = resp.text
                if "```json" in resp_text:
                     resp_text = resp_text.split("```json")[1].split("```")[0].strip()
                ans = json.loads(resp_text)
                enriched["Phase 1 - Real Website vs PBN"] = ans.get("real_website", "")
                enriched["Phase 1 - Topical Match"] = ans.get("topical_match", "")
                enriched["Phase 1 - Content Quality"] = ans.get("content_quality", "")
                enriched["Phase 1 - Write for Us Red Flags"] = ans.get("red_flags", "")
            except Exception as e:
                logging.error(f"   -> Gemini failed: {e}")
                
        # 4. DataForSEO Request (Tokens)
        if enriched["_p2_rank"] == "N/A":
            try:
                logging.info(f"   -> Pinging DataForSEO Backlinks for {domain}")
                url_bl = "https://api.dataforseo.com/v3/backlinks/summary/live"
                req = requests.post(url_bl, json=[{"target": domain}], headers={"Authorization": f"Basic {base64_seo}"})
                data = req.json()
                if data.get("tasks") and data["tasks"][0].get("result") and len(data["tasks"][0]["result"]) > 0:
                    cost_seo = data.get("cost", 0)
                    enriched["_cost_bl"] = cost_seo
                    res = data["tasks"][0]["result"][0]
                    enriched["_p2_rank"] = res.get("rank", "N/A")
                    
                    # Geography
                    countries = res.get("referring_links_countries", {})
                    top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:3]
                    enriched["Phase 2 - Geography"] = ", ".join([f"{c[0]} ({c[1]})" for c in top_countries if c[0]])
                    
                    enriched["Phase 3 - Spam Score"] = res.get("backlinks_spam_score", "N/A")
                    rd = res.get("referring_domains", 0)
                    bl = res.get("backlinks", 1)
                    enriched["Phase 3 - Inbound Ratios"] = f"{rd} RD / {bl} BL"
            except Exception as e:
                logging.error(f"   -> DataForSEO Backlinks failed: {e}")
                
            try:
                logging.info(f"   -> Pinging DataForSEO Traffic for {domain}")
                url_tr = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live"
                post_data_tr = [{"target": domain, "location_code": 2036, "language_code": "en"}]
                req_tr = requests.post(url_tr, json=post_data_tr, headers={"Authorization": f"Basic {base64_seo}"})
                data_tr = req_tr.json()
                cost_tr = data_tr.get("cost", 0)
                enriched["_cost_tr"] = cost_tr
                
                if data_tr.get("tasks") and len(data_tr["tasks"]) > 0:
                    task = data_tr["tasks"][0]
                    if task.get("result") and len(task["result"]) > 0:
                         tr_res = task["result"][0].get("metrics", {}).get("organic", {})
                         enriched["Phase 2 - Traffic Volume"] = tr_res.get("etv", "No Data")
                    else:
                         enriched["Phase 2 - Traffic Volume"] = f"API Message: {task.get('status_message')}"
            except Exception as e:
                logging.error(f"   -> DataForSEO Traffic failed: {e}")
            
        # Assemble Final "Quality Score" column for Google Sheets
        enriched["Quality Score (Phase 1 & 2)"] = f"Rank: {enriched.get('_p2_rank', 'N/A')} | {enriched.get('Phase 1 - Real Website vs PBN', '')} | {enriched.get('Phase 1 - Content Quality', '')}"
        
        # Assemble Cost
        total_seo = enriched.get("_cost_bl", 0.0) + enriched.get("_cost_tr", 0.0)
        enriched["Total Cost (USD)"] = f"${total_seo:.5f}"
        enriched["Cost Breakdown"] = f"DataForSEO Backlinks: ${enriched.get('_cost_bl', 0.0):.5f} | DataForSEO Traffic: ${enriched.get('_cost_tr', 0.0):.5f} | Gemini: Unknown/Free"

        # End Timer
        end_time = time.time()
        enriched["Time Taken (Seconds)"] += round(end_time - start_time, 2)
        
        # 5. SAVE TO CACHE (Save tokens on the next run!)
        cached_data[domain] = enriched
        save_json(cached_data, cache_file)
        
        enriched_prospects.append(enriched)
        
    logging.info("Module 2 Complete.")
    return enriched_prospects
