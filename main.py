import json
import logging
from dotenv import load_dotenv

# Import our 5 modules
from modules.module_1_prospecting import run_module_1
# from modules.module_2_research import run_module_2
from modules.module_3_database import run_module_3
# from modules.module_4_submissions import run_module_4
# from modules.module_5_summary import run_module_5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    with open('config/client_profile_template.json', 'r') as file:
        return json.load(file)

def main():
    # Load Environment Variables (.env)
    load_dotenv(override=True)
    
    # Phase 1: Configuration
    logging.info("Starting Master Automation Blueprint: Link Building & Outreach")
    config = load_config()
    client_site = config['client_details']['website_url']
    logging.info(f"Loaded client profile for: {config['client_details']['business_name']}")

    # Phase 2: The 5-Module Execution Pipeline
    
    logging.info("--- MODULE 1: PROSPECTING ---")
    
    # Create data directory if it doesn't exist
    import os
    os.makedirs('data', exist_ok=True)
    prospects_file = 'data/module_1_prospects.json'
    
    # Check if we already have it to avoid re-running API charges
    if os.path.exists(prospects_file):
        logging.info("Loading previously extracted prospects from disk...")
        with open(prospects_file, 'r') as f:
            master_domain_list = json.load(f)
    else:
        master_domain_list = run_module_1(config['search_parameters'], client_site)
        with open(prospects_file, 'w') as f:
            json.dump(master_domain_list, f, indent=4)
            
    logging.info(f"M1 Summary: Found {len(master_domain_list)} pure organic prospects.")

    logging.info("--- MODULE 2: LINK OPPORTUNITY RESEARCH ---")
    try:
        from modules.module_2_research import run_module_2
        enriched_prospects = run_module_2(master_domain_list[:10])
    except Exception as e:
        logging.error(f"Error in Module 2: {e}")
        enriched_prospects = master_domain_list[:10] # Fallback to raw if script fails
        
    logging.info("--- MODULE 3: DATABASE ENTRY ---")
    try:
        from modules.module_3_database import run_module_3
        # Push the finalized, researched, cached list into Sheets
        run_module_3(enriched_prospects)
    except Exception as e:
        logging.error(f"Error in Module 3: {e}")

    logging.info("--- MODULE 4: TIER 3 DIRECTORY SUBMISSIONS ---")
    # Ask for confirmation (Human in the loop)
    # confirm = input(f"Confirm submission for {config['client_details']['business_name']}? (y/n): ")
    # if confirm.lower() == 'y':
    #     run_module_4(config['client_details'])
    # else:
    #     logging.info("Tier 3 submissions skipped by user")
    logging.info("Skipping M4 (Not implemented yet)")

    logging.info("--- MODULE 5: DAILY SUMMARY ---")
    # summary_data = build_summary(...)
    # run_module_5(summary_data)
    logging.info("Skipping M5 (Not implemented yet)")
    
    logging.info("Automation Pipeline Complete.")

if __name__ == "__main__":
    main()
