import os
from dotenv import load_dotenv
from google import genai

# Force reload the .env file
load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("CRITICAL ERROR: Python cannot find the GEMINI_API_KEY in your .env file.")
else:
    print(f"Loaded Key: {api_key[:10]}... (Length: {len(api_key)})")
    try:
        # Initialize client
        client = genai.Client(api_key=api_key)
        
        # Ping the server
        print("Pinging Gemini servers...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='Reply with the exact words: "API IS ALIVE AND WORKING".'
        )
        print(f"\n✅ SUCCESS! Server responded: {response.text}")
        
    except Exception as e:
        print(f"\n❌ FAILED. Google rejected the request. Error: {e}")