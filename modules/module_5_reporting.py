import os
import json
import logging
from datetime import datetime

REPORT_DIR = "logs"

def run_reporting(targets):
    """
    Module 5: Reporting & Auditing Layer
    Analyzes the run results and generates a structured daily report for executive review.
    """
    logging.info("--- RUNNING MODULE 5 (REPORTING) ---")
    
    os.makedirs(REPORT_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    report_file = os.path.join(REPORT_DIR, f"daily_summary_{today_str}.json")
    
    total_processed = len(targets)
    approved = 0
    rejected = 0
    review = 0
    
    total_cost_api_bl = 0.0
    total_cost_api_tr = 0.0
    total_processing_time = 0.0
    
    tier_1_opportunities = []
    tier_2_opportunities = []
    rejected_domains = []
    
    for p in targets:
        domain = p.get("Domain", "Unknown")
        verdict = p.get("verdict", "")
        
        # Tally verdicts
        if "APPROVED" in verdict:
            approved += 1
        elif "REJECTED" in verdict:
            rejected += 1
            rejected_domains.append(domain)
        elif "REVIEW" in verdict:
            review += 1
            
        # Tally costs & time
        total_cost_api_bl += p.get("_cost_bl", 0.0)
        total_cost_api_tr += p.get("_cost_tr", 0.0)
        total_processing_time += p.get("time_taken", 0.0)
        
        # Tier logic (only if Approved)
        if "APPROVED" in verdict:
            traffic = p.get("Phase 2 - Traffic Volume")
            spam = p.get("Phase 3 - Spam Score")
            
            # Safe parsing
            try:
                tf_val = int(traffic) if traffic is not None else 0
            except:
                tf_val = 0
                
            try:
                spam_val = int(spam) if spam is not None else 0
            except:
                spam_val = 0
                
            # Tier 1 Definition (example): > 1000 traffic and <= 10 spam
            if tf_val > 1000 and spam_val <= 10:
                tier_1_opportunities.append(domain)
            else:
                tier_2_opportunities.append(domain)

    total_cost = total_cost_api_bl + total_cost_api_tr
    
    report = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_domains_processed": total_processed,
        "verdicts": {
            "approved": approved,
            "review": review,
            "rejected": rejected
        },
        "opportunities": {
            "tier_1_count": len(tier_1_opportunities),
            "tier_1_domains": tier_1_opportunities,
            "tier_2_count": len(tier_2_opportunities),
            "tier_2_domains": tier_2_opportunities
        },
        "financials": {
            "total_api_cost_usd": round(total_cost, 5),
            "breakdown": {
                "dataforseo_backlinks_usd": round(total_cost_api_bl, 5),
                "dataforseo_traffic_usd": round(total_cost_api_tr, 5),
                "gemini_usd": 0.0,
            }
        },
        "performance": {
            "total_processing_time_seconds": round(total_processing_time, 2),
            "average_time_per_domain_seconds": round(total_processing_time / total_processed, 2) if total_processed > 0 else 0
        },
        "rejected_domains": rejected_domains
    }
    
    # Save to logs directly
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=4)
        
    # Output quick visual summary to console
    logging.info(f"📊 REPORT GENERATED: {report_file}")
    logging.info(f"   => Approvals: {approved} | Review: {review} | Rejected: {rejected}")
    logging.info(f"   => Tier 1 Gems Found: {len(tier_1_opportunities)}")
    logging.info(f"   => Total API Cost Today: ${total_cost:.5f}")
    
    return report
