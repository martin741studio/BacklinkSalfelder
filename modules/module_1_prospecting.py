import os
import json
import base64
import logging
from urllib.request import Request, urlopen
from urllib.parse import urlparse

def run_module_1(search_parameters, client_website):
    """
    Module 1: Prospecting
    Loops through practice areas and cities, runs a DataForSEO search,
    and returns a deduplicated list of domains.
    """
    logging.info("Starting Prospecting Module (DataForSEO)")

    login = os.getenv("DATAFORSEO_LOGIN")
    password = os.getenv("DATAFORSEO_PASSWORD")

    if not login or not password:
        logging.error("DATAFORSEO_LOGIN or DATAFORSEO_PASSWORD is missing in .env")
        return []

    credentials = f"{login}:{password}"
    base64_bytes = base64.b64encode(credentials.encode("ascii")).decode("ascii")

    master_domain_list = set()
    prospects = [] # Store full objects including ranking URL
    client_domain = get_clean_domain(client_website)

    practice_areas = search_parameters.get('practice_areas', [])
    cities = search_parameters.get('cities', [])

    if not practice_areas or not cities:
        logging.warning("No practice areas or cities found in config.")
        return []

    # Prepare batch post data for DataForSEO
    post_data = []
    task_map = {} # Map task id to query string
    
    task_id = 0
    for city in cities:
        for area in practice_areas:
            keyword = f"{city} {area}"
            task_id += 1
            task_str = str(task_id)
            
            post_data.append({
                "keyword": keyword,
                "location_name": "United States", # Keep location broad and let keyword drive city
                "language_name": "English",
                "depth": 20, # Pull enough to guarantee at least 10 pure organics
                "id": task_str
            })
            task_map[task_str] = keyword

    logging.info(f"Generated {len(post_data)} search queries. Executing one by one...")

    if not post_data:
        return []

    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    
    for task_payload in post_data:
        try:
            req = Request(url, data=json.dumps([task_payload]).encode("utf-8"))
            req.add_header("Authorization", f"Basic {base64_bytes}")
            req.add_header("Content-Type", "application/json")
            
            # Execute request
            response = urlopen(req)
            result_str = response.read().decode("utf-8")
            result_json = json.loads(result_str)

            # Process results
            tasks = result_json.get("tasks", [])
            
            for task in tasks:
                if "status_code" in task and task["status_code"] >= 40000:
                    logging.error(f"Task Failed: {task['status_code']} - {task.get('status_message')}")
                    continue
                    
                task_results = task.get("result", [])
                for res in task_results:
                    keyword_searched = res.get("keyword", "Unknown Query")
                    logging.info(f"Processing SERP for: '{keyword_searched}'")
                    
                    items = res.get("items", [])
                    organic_count = 0
                    
                    for item in items:
                        # We only care about organic results
                        if item.get("type") == "organic":
                            url_rank = item.get("url")
                            domain = item.get("domain")
                            
                            if not url_rank or not domain:
                                continue
                                
                            clean_domain = get_clean_domain(domain)
                            
                            # Stop if we hit 10 organic results per query
                            if organic_count >= 10:
                                break
                                
                            # Skip client domain
                            if clean_domain == client_domain:
                                logging.debug(f"Skipping client domain: {clean_domain}")
                                continue
                                
                            # Deduplicate across the entire master list
                            if clean_domain not in master_domain_list:
                                master_domain_list.add(clean_domain)
                                prospects.append({
                                    "domain": clean_domain,
                                    "url": url_rank,
                                    "source_query": keyword_searched
                                })
                            organic_count += 1

        except Exception as e:
            logging.error(f"Error calling DataForSEO API for '{task_payload['keyword']}': {e}")

    logging.info(f"Module 1 Complete: Found {len(prospects)} unique domains from {len(post_data)} queries.")
    return prospects

def get_clean_domain(url_str):
    """
    Extracts purely the root domain (e.g. example.com) to prevent duplicates
    like www.example.com vs example.com
    """
    if not url_str.startswith("http"):
        url_str = "http://" + url_str
    
    parsed = urlparse(url_str)
    domain = parsed.netloc.lower()
    
    # Remove www.
    if domain.startswith("www."):
        domain = domain[4:]
        
    return domain

# For local testing if ran directly
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    
    # Mock parameters
    params = {
        "practice_areas": ["personal injury"],
        "cities": ["Phoenix"]
    }
    client_site = "https://www.examplelaw.com"
    results = run_module_1(params, client_site)
    print(json.dumps(results, indent=2))
