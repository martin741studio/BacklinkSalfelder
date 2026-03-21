import os
import json
import logging

# Hardcoded Global Blocklist
BLOCKED_DOMAINS = [
    "tripadvisor.com",
    "klook.com",
    "booking.com",
    "agoda.com",
    "airbnb.com",
    "expedia.com",
    "yelp.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "medium.com",
    "pinterest.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "groupon.com",
    "foursquare.com"
]

WEB2_PATTERNS = [
    "tripadvisor",
    "booking",
    "klook",
    "expedia",
    "review",
    "directory",
    "list",
    "top-10",
    "top10",
    "best-",
    "best10",
    "jameda",
    "sanego",
    "gelbeseiten",
    "dasoertliche",
    "11880",
    "branchenbuch",
    "telefonbuch",
    "kennstdueinen",
    "arzt-auskunft",
    "werkenntdenbesten",
    "doctolib"
]

DENY_LIST_FILE = "/tmp/deny_list.json"

def load_deny_list():
    if not os.path.exists(DENY_LIST_FILE):
        return set()
    try:
        with open(DENY_LIST_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get("blocked", []))
    except Exception as e:
        logging.error(f"Error loading deny list: {e}")
        return set()

def add_to_deny_list(domain):
    delay_list = load_deny_list()
    if domain not in delay_list:
        delay_list.add(domain)
        try:
            os.makedirs(os.path.dirname(DENY_LIST_FILE), exist_ok=True)
            with open(DENY_LIST_FILE, 'w') as f:
                json.dump({"blocked": list(delay_list)}, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving to deny list: {e}")

def is_blocked_domain(domain):
    """
    Returns True if the domain is a known marketplace, social profile, directory, or pattern match.
    """
    domain_lower = domain.lower()
    
    # Check manual deny list (JSON state)
    persistent_deny_list = load_deny_list()
    if domain_lower in persistent_deny_list:
        return True
        
    # Check static hardcoded list
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain_lower:
            return True
            
    # Check Web 2.0 / Aggregator patterns
    for pattern in WEB2_PATTERNS:
        if pattern in domain_lower:
            return True
            
    return False

if __name__ == "__main__":
    # Test cases
    test_domains = [
        "cangguwellness.com",
        "tripadvisor.com.au",
        "bali-reviews-top-10.com",
        "x.com/bali",
        "independent-travel-blog.com"
    ]
    for d in test_domains:
        print(f"{d} -> Blocked? {is_blocked_domain(d)}")
