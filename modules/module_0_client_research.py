import os
import json
import logging
import requests
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from google import genai

def scrape_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        if not url.startswith('http'):
            url = 'https://' + url
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        clean_text = ' '.join(text.split())[:8000] # limit to 8000 chars roughly
        return clean_text, soup, url
    except Exception as e:
        logging.error(f"Failed to scrape {url}: {e}")
        return "", None, url


def run_client_research(website_url, gbp_url="", fields_dict=None):
    """
    Acts as a persistent data extraction and sheet population agent for new clients.
    """
    logging.info(f"--- RUNNING CLIENT RESEARCH AGENT ---")
    logging.info(f"Website: {website_url} | GBP: {gbp_url}")
    
    if fields_dict is None:
        fields_dict = {}
        
    # 1. Scrape the Main Website
    main_text, soup, base_url = scrape_url(website_url)
    
    # 2. Try to find and scrape the Contact page briefly
    contact_text = ""
    if soup:
        contact_links = []
        for a in soup.find_all('a', href=True):
            if 'contact' in a['href'].lower() or 'about' in a['href'].lower() or 'kontakt' in a['href'].lower():
                contact_links.append(urljoin(base_url, a['href']))
        
        if contact_links:
            target_contact = contact_links[0]
            logging.info(f"Found related page to scrape: {target_contact}")
            ctext, _, _ = scrape_url(target_contact)
            contact_text = ctext[:4000]

    combined_text = main_text
    if contact_text:
        combined_text += "\n\n--- CONTACT/ABOUT PAGE TEXT ---\n\n" + contact_text

    # 3. Query Gemini
    api_key_gemini = os.getenv("GEMINI_API_KEY")
    if not api_key_gemini:
        logging.error("No Gemini API key found. Cannot perform research.")
        return None

    client = genai.Client(api_key=api_key_gemini)
    
    prompt = f"""
You are an autonomous client research and spreadsheet enrichment agent.

Your job is to process rows from a structured spreadsheet and COMPLETE ALL REQUIRED FIELDS for each business.

You are NOT allowed to skip fields.

-----------------------------------
CRITICAL RULES (HIGHEST PRIORITY)
-----------------------------------

1. LANGUAGE CONSISTENCY
- Detect the language used in the sheet (e.g. German or English)
- ALL outputs MUST be written in that same language
- Do NOT mix languages

2. COMPLETE EXECUTION
- You MUST process ALL columns/fields defined in the JSON I pass you.
- You are NOT allowed to stop early.
- You are NOT allowed to skip sections even if partial data exists.

3. FORMATTING (NO HARD BRACKETS)
- DO NOT use hard brackets [] in your string outputs. Return items as comma-separated lists or natural language bullet points (-).
- Example BAD: ["Service 1", "Service 2"]
- Example GOOD: Service 1, Service 2

4. EXISTING DATA HANDLING
- If a field already contains:
  → example text (like "z.B. ...", "optional", "ja/nein", "TRUE/FALSE", etc) → IGNORE it and replace with real metadata.
  → partial data → IMPROVE and COMPLETE it

5. FIELD TYPE DEFINITIONS (CRITICAL)
1. DYNAMIC FIELDS (MANDATORY TO FILL)
- Point 4 (Zielpartner-Definition): The input contains generic examples like "Ärzte/Kliniken". For EACH of these, you MUST output ONLY your highly customized suggestions specific to this exact client! These will be added into an "Additional/Weitere" column! Example: If the client is a dentist focusing on children, just output "→ Kitas, Grundschulen, Kinderärzte". DO NOT return the original generic text.
- Sub-Niches (Sub-Nische) & USP
- Bottlenecks (Schwachstellen) & Opportunities (Potenziale) (Generate min 3 if empty/not present)

2. CONDITIONAL FIELDS (EVALUATE)
- DR score/Traffic: DO NOT guess this. If I ask you for it, return "Not Found" or empty string since I do this manually now.
- Yes/No qualification checks

-----------------------------------
OUTPUT FORMAT
-----------------------------------

Return ONLY valid JSON. The JSON Keys MUST exactly match the names of the requested fields provided below. Do NOT change the keys.

--- INPUT DATA ---
Website URL: {website_url}
Google Business Profile URL: {gbp_url}

--- REQUESTED FIELDS (THESE MUST BE THE KEYS IN YOUR JSON) ---
{json.dumps(fields_dict, indent=2, ensure_ascii=False)}

--- SCRAPED CONTEXT FROM WEBSITE ---
{combined_text[:12000]}
"""

    try:
        logging.info("Sending prompt to Gemini...")
        resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        resp_text = resp.text
        
        # Clean JSON markdown if attached
        if "```json" in resp_text:
             resp_text = resp_text.split("```json")[1].split("```")[0].strip()
        elif "```" in resp_text:
             resp_text = resp_text.split("```")[1].split("```")[0].strip()
             
        data = json.loads(resp_text)
        logging.info("Successfully parsed Gemini JSON.")
        return data
    except Exception as e:
        logging.error(f"Failed to generate or parse response from Gemini: {e}")
        return None
