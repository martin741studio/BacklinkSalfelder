---
description: Autonomous prospecting agent that finds, vets, and logs link opportunities. It scrapes domains, analyzes relevance and quality, pulls SEO metrics via DataForSEO, caches results to avoid duplicate API calls, and stores structured data in a central da
---


741 Studio – Agent Rules Book

Prospecting & Link Opportunity Pipeline

This rules book defines the operational constraints, execution protocols, and data governance rules for all agents operating inside the pipeline.

The primary goals are:
	•	Prevent duplicate work
	•	Prevent unnecessary API usage
	•	Preserve data consistency
	•	Ensure deterministic workflows
	•	Maintain reproducibility for new clients

⸻

1. Core Operating Principles

Agents must always prioritize:
	1.	Data reuse over re-scraping
	2.	Deterministic workflows
	3.	API cost efficiency
	4.	Data consistency
	5.	Clear phase execution

Agents must never repeat work if a verified result already exists.

⸻

2. Single Source of Truth (SSOT)

Every domain must exist in exactly one canonical record.

Primary key:

domain

Example:

example.com

All modules must reference this field.

Agents are not allowed to create duplicate entries for the same domain.

Before performing any action, the agent must:
	1.	Check if the domain already exists in the dataset
	2.	If yes → load existing record
	3.	Only run missing phases

⸻

3. API Usage Rules (Token Protection)

APIs are expensive and must follow strict usage rules.

Rule 1 — Never re-query the same domain

Before calling:
	•	DataForSEO
	•	AI model
	•	scraping engine

The agent must check:

data/cache/

or the spreadsheet/database.

If the domain has already been processed:

skip API call
load cached result


⸻

Rule 2 — Cache everything

Every external call must create a cached record.

Example:

cache/domain_analysis/example.com.json

Contents:

homepage_text
emails_found
ai_quality_score
spam_score
traffic
backlink_ratio
timestamp

If the script crashes, the system must resume from cache.

⸻

Rule 3 — One AI call per domain maximum

Gemini analysis must only run once.

Agents must store:

ai_analysis_complete = true

If true → never call again.

⸻

4. Phase Execution Protocol

The pipeline must follow strict phase order.

Phase 0 → Domain Discovery
Phase 1 → Qualitative Screening
Phase 2 → Traffic & Geography
Phase 3 → SEO Risk Analysis
Phase 4 → Database Entry

Agents are forbidden from skipping phases.

However:

if phase already completed → skip


⸻

5. Column Stability Rules (Critical)

The agent must never rely on column order.

Instead, it must always reference column names.

Example:

Correct:

row["domain"]
row["phase1_topical_match"]
row["phase2_traffic"]

Incorrect:

row[1]
row[4]

This prevents failures when column order changes.

⸻

6. Domain Processing Lock

To prevent duplicate work in multi-agent systems.

Before processing:

domain_status = "processing"

After completion:

domain_status = "complete"

If another agent encounters:

domain_status = processing

It must skip the domain.

⸻

7. Red Flag Detection Rules

Phase 1 includes disqualification signals.

The agent must immediately mark:

phase1_status = rejected

if any of the following phrases appear:

we do not accept guest posts
no guest submissions
no advertising inquiries
paid posts not accepted
sponsored content not allowed

If rejected:

skip phases 2 and 3

This saves tokens.

⸻

8. Traffic Data Governance (DataForSEO)

Traffic must only be pulled once per domain.

Required metrics:

traffic_volume
domain_rank
referring_domains
total_backlinks
spam_score

Inbound ratio must be calculated as:

referring_domains / total_backlinks

Agents must never call Ahrefs or any alternative metric source.

All metrics must come from DataForSEO to ensure consistency.

⸻

9. Time Tracking

Each domain record must include:

time_started
time_completed
processing_duration

Processing duration is calculated automatically.

Purpose:
	•	detect bottlenecks
	•	optimize scraping

⸻

10. Email Extraction Rules

Homepage scraping must:
	1.	Extract visible emails
	2.	Extract hidden mailto links
	3.	Scan contact page if homepage fails

Only if no email found after these steps should the agent record:

email = null

No repeated scraping allowed.

⸻

11. Error Recovery Protocol

If a module fails:
	1.	Write error log
	2.	Mark domain

status = error

	3.	Continue with next domain

The pipeline must never stop completely.

⸻

12. Logging Rules

Every module must produce logs.

Example:

logs/module_2/
logs/module_3/

Each log entry must include:

timestamp
domain
action
result
errors


⸻

13. Client Isolation Rule

Every client must run inside its own directory.

Structure:

clients/
   client_01/
      prospects.json
      cache/
      logs/
   client_02/
      prospects.json
      cache/
      logs/

Agents must never mix data between clients.

⸻

14. Execution Limits

To prevent runaway agents:

Maximum per run:

100 domains discovered
30 domains vetted
10 API calls per minute

If limits are reached:

pause execution
resume next cycle


⸻

15. Safe Resume System

If the script stops unexpectedly:

The system must resume using:

last_processed_domain

Agents must continue from the next domain.

⸻

16. Directory Automation Rules (Module 4)

When submitting to directories:

Agents must:
	•	confirm business listing page
	•	confirm category match
	•	avoid duplicate submissions

If listing already exists:

skip


⸻

17. Reporting Rules (Module 5)

Daily report must include:

new domains discovered
domains rejected
tier 1 opportunities
tier 2 opportunities
errors
API usage

This ensures visibility without opening logs.

⸻

18. Anti-Loop Protection

Agents must never repeat the same operation more than:

2 attempts

If the second attempt fails:

log error
skip domain


⸻

19. Deterministic Output Format

All modules must return structured JSON objects.

Example:

{
 "domain": "example.com",
 "phase1_topical_match": true,
 "phase2_traffic": 3200,
 "spam_score": 2,
 "email": "contact@example.com"
}

No free text allowed.

⸻

20. Agent Responsibility Map

Each module must only do its assigned task.

Module	Responsibility
Module 1	Domain discovery
Module 2	Quality vetting
Module 3	Database entry
Module 4	Directory submissions
Module 5	Reporting

Modules must not perform tasks outside their scope.

⸻

The Most Important Rule (for token cost)

Agents must always ask:

“Do I already have this data?”

If yes:

load
skip API
continue pipeline


⸻

💡 One more rule I strongly recommend for your system

Add a Domain Knowledge File:

domain_registry.json

This becomes the master memory for every domain ever processed.

That way when you run campaigns for multiple clients, the system already knows:

spam sites
good publishers
directories
irrelevant domains

This will reduce your scraping cost massively over time.

21. Token Protection Rule (Never Spend Tokens Twice)

External APIs must never be called if valid data already exists locally.

The agent must always perform a local cache check before any external request.

Execution order:

1. Check cache
2. Check database
3. Only then call API

If cached data exists:

skip API call
load cached data


⸻

Module-Level Implementation

Module 1 — Prospect Search Cache

Search results must be cached to:

data/module_1_prospects.json

When main.py starts:

if cache file exists:
    load results
else:
    run DataForSEO search

Only query DataForSEO if the cache file is missing.

⸻

Module 2 — Partial Checkpoint Cache

Deep research must be cached in:

data/module_2_cache.json

Each domain must store partial completion states.

Example structure:

{
  "example.com": {
    "scrape_complete": true,
    "gemini_complete": false,
    "dataforseo_complete": true
  }
}

If a task was already completed, the agent must skip that block.

Example:

if dataforseo_complete == true
skip DataForSEO call

This prevents paying twice when the script resumes.

⸻

22. Duplicate Prevention Rule (CRM Integrity)

The system must never insert duplicate domains into the CRM.

Before writing to Google Sheets:

Module 3 must fetch all existing domains from:

Column A

Execution logic:

if domain already exists in sheet:
    skip entry

Only domains that are not already present may be appended.

This ensures:
	•	clean CRM
	•	reliable reporting
	•	no repeated outreach

⸻

23. API Rate Limit Protection

APIs have request-per-minute limits and must not be overwhelmed.

DataForSEO

Requests must be spaced to prevent rate limits.

Recommended safeguard:

sleep 1–2 seconds between calls


⸻

Gemini AI

Typical limit:

~15 requests per minute

To avoid 429 errors:

sleep 4 seconds between AI calls

If a quota error occurs:

pause pipeline
retry after delay


⸻

24. Web Scraping Anti-Blocking Rule

All HTTP requests must include a browser header so websites treat the script like a real browser.

Example header:

User-Agent: Mozilla/5.0

Without this header many websites will block Python scripts immediately.

⸻

Scaling Rule

If scraping volume exceeds:

100 websites per run

the agent must implement:

sleep 2 seconds between scrapes

Purpose:
	•	prevent IP blocking
	•	avoid DDoS detection

⸻

25. Graceful Degradation Rule (Pipeline Stability)

A single broken domain must never stop the pipeline.

Each external operation must be wrapped in error handling.

Required for:
	•	Web scraping
	•	Gemini analysis
	•	DataForSEO queries

Example logic:

try:
    scrape website
except:
    mark site as offline
    continue

If a domain fails:

status = "site_offline"

The pipeline must continue with the next domain.

⸻

26. Web Scraper Timeout Rule

Web requests must never wait indefinitely.

All HTTP requests must include:

timeout = 10 seconds

If timeout occurs:

status = timeout
skip domain

This prevents the pipeline from freezing.

⸻

27. Client Self-Exclusion Rule

The system must never process the client’s own domain.

Module 1 must load the client URL from:

client_profile_template.json

Example:

client_domain = exampleclient.com

During search result cleaning:

remove client_domain

This prevents:
	•	self-scraping
	•	self-outreach
	•	self-link requests

⸻

28. Domain Processing Priority

Domains must be processed sequentially.

Processing order:

domain_1
domain_2
domain_3

Parallel execution is not allowed unless rate-limit controls are implemented.

Purpose:
	•	prevent API bursts
	•	reduce token spikes
	•	avoid server blocking

⸻

29. Safe Restart Protocol

If the script stops unexpectedly, the system must restart safely.

Steps:

1. Load cache
2. Load processed domains
3. Skip completed domains
4. Resume at next unfinished domain

No completed domain may be reprocessed.

⸻

30. Failure Logging Rule

Every failure must be recorded.

Required log fields:

timestamp
domain
module
error_type
action_taken

Logs must be stored in:

logs/pipeline.log

This allows debugging without rerunning the entire pipeline.

⸻

31. Processing Efficiency Tracking

Each domain must track processing time.

Required fields:

time_started
time_completed
duration_seconds

Processing duration is calculated automatically.

Purpose:
	•	detect slow modules
	•	optimize scraping speed
	•	measure token efficiency


⸻

32. Cost Tracking & Transparency

Every API call must be mathematically tracked per domain.

Required output fields:

total_cost_usd
cost_breakdown

For DataForSEO:
Agents must parse the "cost" metric natively returned in the JSON payload of every endpoint.

For Gemini:
Agents must log it as "Gemini: Free" (or correctly parse the billing calculation if upgrading).

This ensures real-time visibility into the exact financial burn rate of the automation pipeline.

⸻

33. Append-Only Database Rule (No Deletions)

Agents are strictly forbidden from clearing, erasing, or wiping the main Google Sheet (or any other primary CRM).

All database operations must be configured to Append New Rows Only.
If corrupted data exists, it must either be fixed manually row-by-row or skipped. Whole-sheet wipes are permanently banned to prevent the accidental loss of manually verified outreach contacts or historical data.
