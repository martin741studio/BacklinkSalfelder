import os
import json
import logging
import time
import requests
from bs4 import BeautifulSoup
from google import genai
from pydantic import BaseModel, Field

# Load cache
CACHE_FILE = "/tmp/module_4_cache.json"

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                if data.get("_version") != "v1":
                    return {"_version": "v1"}
                return data
        except Exception:
            return {"_version": "v1"}
    return {"_version": "v1"}

def save_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

class PositioningResponse(BaseModel):
    factual_points: list[str] = Field(description="Exactly 3 specific factual points or insights about the domain")
    confidence_score: int = Field(description="Confidence Score (0-100) based on relevance, authority, and collaboration potential")

class OutputResponse(BaseModel):
    subject: str = Field(description="The catchy, non-clickbaity email subject line")
    body: str = Field(description="The full email body pitching a guest post or partnership based on context")



def run_outreach(targets, client_profile):
    logging.info("--- RUNNING MODULE 4 (OUTREACH ASSEMBLY) ---")
    cache = load_json(CACHE_FILE)
    api_key_gemini = os.getenv("GEMINI_API_KEY")
    
    if not api_key_gemini:
        logging.error("No Gemini API key found in .env. Skipping Outreach Module.")
        return targets
        
    client = genai.Client(api_key=api_key_gemini)
    
    business_desc = client_profile.get("client_details", {}).get("business_description", "A local business")
    business_name = client_profile.get("client_details", {}).get("business_name", "Our Company")
    website_url = client_profile.get("client_details", {}).get("website_url", "")
    
    out = []
    
    for p in targets:
        d_name = p.get("Domain", "")
        url = p.get("URL (Domain)", p.get("url", d_name))
        
        # We check if the orchestrator marked it as APPROVED and SEND-READY
        verdict = p.get("verdict", "")
        contact_info = (p.get("Contact") or "").strip()
        first_name = (p.get("First Name") or "").strip()
        last_name = (p.get("Last Name") or "").strip()
        
        if "REJECTED" in verdict:
            logging.info(f"Skipping M4 Reach -> Verdict is REJECTED.")
            p["Outreach Subject"] = None
            p["Outreach Body"] = None
            p["3 Helpful Factual Points"] = None
            p["Confidence Score"] = None
            out.append(p)
            continue
            
        cached_m4 = cache.get(d_name, {})
        
        # Hydrate p from M4 cache if it already executed successfully
        if cached_m4.get("_outreach_done"):
            logging.info(f"Skipping M4 Outreach -> already completed in cache.")
            p["Outreach Subject"] = cached_m4.get("subject")
            p["Outreach Body"] = cached_m4.get("body")
            p["3 Helpful Factual Points"] = cached_m4.get("factual_points")
            p["Confidence Score"] = cached_m4.get("confidence_score")
            p["_outreach_done"] = True
            out.append(p)
            continue
            
        logging.info(f"   -> [Phase 5: Positioning] Fetching target details directly for {d_name} (NO HTTP CALLS)")

        # 2. Prompt Gemini
        # 1. Positioning Phase (For both REVIEW and APPROVED)
        positioning_sys = (
            "You are evaluating a website for a B2B collaboration. Your goal is to strictly extract "
            "actionable relevance points and assign a confidence score based on the provided signals."
            "STRICTLY RESPOND IN GERMAN."
        )
        
        positioning_prompt = f"""
        Analyze the following domain and return:
        1) a confidence score from 0–100
        2) exactly 3 highly specific factual insights for outreach positioning

        IMPORTANT:
        - Only use the provided data
        - No assumptions
        - No generic statements
        - No fluff

        DATA:
        Domain: {d_name}
        Content Summary: {p.get('Phase 1 - Topical Match', 'N/A')}
        Traffic Data: {p.get('Phase 2 - Traffic Volume', 'N/A')}
        Backlink Data: {p.get('Phase 3 - Inbound Ratios', 'N/A')}

        SCORING LOGIC:
        - High score = strong collaboration potential, relevant audience, solid authority
        - Mid score = unclear or moderate fit
        - Low score = weak or irrelevant
        - NOTE: If Traffic Data is 'None' or 0, DO NOT heavily reduce the score. This is completely normal for local, physical brick-and-mortar businesses.

        FACTUAL POINT RULES:
        - Must be specific and grounded in the data
        - Must highlight audience, content, or SEO signals
        - Must be usable in outreach

        BAD:
        - 'Looks professional'
        - 'Good website'
        - 'Strong presence'

        GOOD:
        - 'Ranks for local service queries indicating regional relevance'
        - 'Publishes content around health topics showing topical overlap'
        - 'Backlink profile includes niche-relevant domains'
        """
        
        try:
            pos_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=positioning_prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': PositioningResponse,
                    'system_instruction': positioning_sys,
                    'temperature': 0.7
                }
            )
            data_pos = json.loads(pos_response.text)
            
            p["3 Helpful Factual Points"] = "\n".join([f"- {pt}" for pt in data_pos.get("factual_points", [])])
            p["Confidence Score"] = data_pos.get("confidence_score")
            
            # If REVIEW, we stop here.
            if "REVIEW" in verdict:
                logging.info(f"   -> Verdict is REVIEW. Halting at Positioning Phase.")
                p["Outreach Subject"] = None
                p["Outreach Body"] = None
                p["_outreach_done"] = True
                
                cached_m4["subject"] = None
                cached_m4["body"] = None
                cached_m4["factual_points"] = p["3 Helpful Factual Points"]
                cached_m4["confidence_score"] = p["Confidence Score"]
                cached_m4["_outreach_done"] = True
                cache[d_name] = cached_m4
                save_json(cache, CACHE_FILE)
                out.append(p)
                continue
                
            # If APPROVED, we proceed to Output Phase
            logging.info(f"   -> [Phase 6: Output Generation] Constructing email for APPROVED lead {d_name}")
            
            sys_instructions = (
                "You are aggressively focused on creating a clear, value-driven collaboration pitch that gets a reply. "
                "Your goal is NOT to be overly polite or purely descriptive; you are an equal peer offering distribution, exposure, and growth. "
                "TONE RULES:\n"
                "- Low-friction, value-driven, and extremely easy to respond to.\n"
                "- NO attacking, criticizing, or auditing their website.\n"
                "- NO explaining their own business to them.\n"
                "- NO 'we noticed...' or 'Uns ist aufgefallen...' style phrasing.\n"
                "- BAN WEAK LANGUAGE: Never use 'vielleicht', 'wir dachten', oder 'könnte'. Be highly confident and direct.\n"
                "- Never use generic greetings like 'Dear Webmaster'.\n"
                "- ABSOLUTE FORMATTING RULE: You MUST output proper email paragraphs separated by double newlines (\\n\\n). Do NOT output a single wall of text!\n"
                "Keep it strictly under 120-150 words. "
                "STRICTLY RESPOND IN GERMAN."
            )
            
            if first_name and last_name:
                greeting_instruction = f"Strictly write: 'Sehr geehrte(r) {first_name} {last_name},'"
            elif last_name:
                greeting_instruction = f"Strictly write: 'Sehr geehrte(r) Herr/Frau {last_name},'"
            elif first_name:
                greeting_instruction = f"Strictly write: 'Hallo {first_name},'"
            else:
                greeting_instruction = f"Extract the clean brand name from '{d_name}' (remove .de, .com) and strictly write: 'Sehr geehrte Damen und Herren von [Brand Name],'"
            
            custom_points_text = (
                "\n!!! ABSOLUTE REQUIREMENT: CORE PERSONALIZATION !!!\n"
                "Use the following 3 crafted points we extracted to actively shape the hook, the value proposition, and the collaboration angle organically.\n"
                f"POINTS:\n{p['3 Helpful Factual Points']}\n"
                "!!! END OF REQUIREMENT !!!\n"
            )
            
            output_prompt = f"""
            We are contacting website: {d_name} on behalf of {business_name} ({business_desc}).
            
            {custom_points_text}
            
            ## CORE OBJECTIVE
            Generate an email in GERMAN that:
            - feels highly relevant to the recipient
            - clearly communicates WHAT THEY GAIN
            - clearly communicates HOW the collaboration works (content + backlinks)
            
            ## CRITICAL EXECUTION RULES
            1. USE EXACTLY ONE ANGLE FROM THE POINTS PROVIDED (Select strongest)
            2. TRANSLATE SIGNAL -> REAL-WORLD SITUATION
            3. CONNECT TO CLEAR BENEFIT (mehr lokale Sichtbarkeit, Zugang zu neuen relevanten Kunden/Zielgruppen, stärkere Positionierung)
            4. MAKE THE COLLABORATION EXPLICIT (e.g. "durch gemeinsame Content-Platzierungen und Verlinkungen")
            5. KEEP IT SIMPLE AND DIRECT (No over-explaining)
            6. DO NOT sound like a consultant audit
            
            ## REQUIRED STRUCTURE
            Follow EXACTLY this flow, using double newlines (\\n\\n) to create clear, readable paragraphs between each section:
            
            1. INTRO
               - {greeting_instruction}
               - wer wir sind (Werbeagentur Bamberger) und wen wir repräsentieren (Zahnarztpraxis Dr. Salfelder)
            
            2. RELEVANCE & VALUE
               - Combine the strongest factual point into a real-world situation.
               - State clearly what they gain (mehr lokale Sichtbarkeit, Zugang zu neuen relevanten Kunden/Zielgruppen).
            
            3. MECHANISM
               - Explicitly mention the collaboration (e.g., "Wir möchten Ihnen eine Content-Kooperation vorschlagen. Durch gemeinsame Content-Platzierungen und Verlinkungen können wir...")
            
            4. CTA
               - Use ONLY: "Ist das grundsätzlich interessant für Sie?", "Falls das für Sie interessant klingt, reicht eine kurze Rückmeldung.", or "Passt das grundsätzlich für Sie?"
            
            ## SUBJECT LINE RULES
            - BANNED: "Kurze Frage", "Synergie", "Gastartikel", "SEO", "Linkaufbau".
            - PREFERRED: "Zusammenarbeit", "Austausch", "Gemeinsames Projekt", "Partnerschaft".
            - FORMAT: Write naturally. Extract 1 keyword directly from the chosen angle. Under 6 words.
            
            ## FINAL CHECK BEFORE OUTPUT
            - Are there clear paragraph breaks (\\n\\n)?
            - Does it sound completely natural and native in German?
            - Is the collaboration clearly stated? 
            If any answer = NO -> rewrite.
            """
            
            output_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=output_prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': OutputResponse,
                    'system_instruction': sys_instructions,
                    'temperature': 0.7
                }
            )
            data_out = json.loads(output_response.text)
            
            p["Outreach Subject"] = data_out.get("subject")
            p["Outreach Body"] = data_out.get("body")
            p["_outreach_done"] = True
            
            # Save mapping to local M4 Cache
            cached_m4["subject"] = p["Outreach Subject"]
            cached_m4["body"] = p["Outreach Body"]
            cached_m4["factual_points"] = p["3 Helpful Factual Points"]
            cached_m4["confidence_score"] = p["Confidence Score"]
            cached_m4["_outreach_done"] = True
            cache[d_name] = cached_m4
            save_json(cache, CACHE_FILE)
            
            time.sleep(2) # rate limit safety
            
        except Exception as e:
            logging.error(f"Failed to generate assets for {d_name}: {e}")
            p["Outreach Subject"] = None
            p["Outreach Body"] = None
            if "3 Helpful Factual Points" not in p: p["3 Helpful Factual Points"] = None
            if "Confidence Score" not in p: p["Confidence Score"] = None
            p["_outreach_done"] = False
            
        out.append(p)
        
    return out
