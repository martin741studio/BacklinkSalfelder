# Master Automation Blueprint: Link Building & Outreach System

## 1. Local Setup Instructions

### Environment
1. Open a terminal in this directory.
2. Create and activate a Virtual Environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install Python dependencies:
   ```bash
   pip3 install -r requirements.txt
   playwright install
   ```
3. Copy `.env.example` to a new file named `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```

### 2. Google Sheets API Configuration
Because this script runs locally and interacts with your Google account on your behalf, we need to create an OAuth2 or Service Account credential. Since you want to copy the template, a Service Account is best.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a New Project (e.g., "Backlink Automation").
3. Go to **APIs & Services > Library**, search for "Google Sheets API" and "Google Drive API", and **Enable** both.
4. Go to **APIs & Services > Credentials**.
5. Click **Create Credentials > Service Account**.
6. Name it (e.g., "Sheet Writer").
7. Click into the new Service Account, go to the **Keys** tab, click **Add Key > Create New Key > JSON**.
8. Save that JSON file into the `config/` folder of this project and rename it to `credentials.json`.
9. **IMPORTANT STEP:** Open your Master Google Sheet in your browser. Click "Share" and share it with the exact `client_email` found inside your `credentials.json` file. Provide it "Editor" access.

Now the script can read/write to your sheet!

### 3. API Keys
*   **LLM (Gemini):** Go to Google Cloud / AI Studio to grab your Gemini API key.
*   **DataForSEO (Search Engine & Traffic Metrics):** Get your API credentials (login and password) from the DataForSEO dashboard. We use this for both prospecting and traffic estimation.
*   **Email:** Use a Google App Password to avoid locking your Gmail account.

## Executing the System
You manage client data inside the `config/client_profile_template.json` structure (save as `client_profile.json`). To run the entire pipeline:

```bash
python main.py
```
