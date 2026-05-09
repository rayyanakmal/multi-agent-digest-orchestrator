"""One-time OAuth2 authorisation flow for Google Drive access.

Run this once:
    python setup_google_oauth.py

It will open a browser, ask you to log in with your Google account,
and save the token to credentials/google-oauth-token.json.
After that, the daily digest pipeline will use that token automatically.

Requirements:
  - credentials/google-oauth-client.json  (Desktop OAuth client from GCP console)
"""
import os, sys, json
from pathlib import Path

BASE = Path(__file__).parent
CLIENT_FILE = BASE / "credentials" / "google-oauth-client.json"
TOKEN_FILE = BASE / "credentials" / "google-oauth-token.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

if not CLIENT_FILE.exists():
    print(f"""
[ERROR] OAuth client file not found: {CLIENT_FILE}

To create one:
  1. Go to https://console.cloud.google.com/apis/credentials?project=daily-digest-app-495805
  2. Click "+ Create Credentials" → "OAuth client ID"
  3. Application type: Desktop app
  4. Download the JSON and save it as:
     {CLIENT_FILE}

Then re-run this script.
""")
    sys.exit(1)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    sys.exit("[ERROR] Missing package. Run: pip install google-auth-oauthlib")

print("Starting OAuth flow — a browser window will open...")
flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
creds = flow.run_local_server(port=0, open_browser=True)

TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
TOKEN_FILE.chmod(0o600) if TOKEN_FILE.exists() else None
with open(TOKEN_FILE, "w") as f:
    f.write(creds.to_json())
TOKEN_FILE.chmod(0o600)

print(f"\n✅  Token saved to {TOKEN_FILE}")
print("You can now run the full pipeline:\n  python -m src.runtime.entrypoint")
