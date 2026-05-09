"""Isolated Google Drive upload test — run before full pipeline."""
import io, os, sys, json
from pathlib import Path

BASE = Path(__file__).parent
CREDS = BASE / "credentials" / "google-service-account.json"

# 1. Sanity checks
print("=== Pre-flight checks ===")
if not CREDS.exists():
    sys.exit(f"[FAIL] Credentials file missing: {CREDS}")
print(f"[OK]  Credentials file found: {CREDS}")
with open(CREDS) as f:
    cred_data = json.load(f)
print(f"[OK]  Service account: {cred_data.get('client_email', 'UNKNOWN')}")
print(f"[OK]  Project: {cred_data.get('project_id', 'UNKNOWN')}")

# 2. Load settings
sys.path.insert(0, str(BASE))
from src.config.settings import Settings
settings = Settings()
folder_id = settings.google_drive_folder_id
print(f"[OK]  Drive folder ID: {folder_id}")

# 3. Initialize adapter
print("\n=== Initializing GoogleDriveAdapter ===")
try:
    from src.adapters.google_drive import GoogleDriveAdapter
    adapter = GoogleDriveAdapter(credentials_path=str(CREDS), folder_id=folder_id)
    print("[OK]  Adapter initialized")
except Exception as e:
    sys.exit(f"[FAIL] Could not initialize adapter: {e}")

# 4. Test folder access
print("\n=== Testing Drive folder access ===")
try:
    result = adapter.drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id,name)",
        pageSize=5,
    ).execute()
    files = result.get("files", [])
    print(f"[OK]  Folder accessible — {len(files)} existing file(s): {[f['name'] for f in files]}")
except Exception as e:
    sys.exit(f"[FAIL] Cannot list folder contents: {e}")

# 5. Build minimal test digest
from src.models.contracts import DigestOutput, SummaryItem
test_digest = DigestOutput(
    date="2026-05-09",
    title="Daily AI & Tech Digest — 2026-05-09 [TEST]",
    top_takeaways=[
        "Drive upload is working correctly.",
        "Service account has Editor access on target folder.",
    ],
    article_summaries=[
        SummaryItem(
            title="Test Article",
            source="test-drive-upload.py",
            url="https://example.com",
            summary="This is a test summary written by the isolated Drive upload test script.",
            tags=["test", "drive"],
        )
    ],
    total_articles_reviewed=1,
    llm_model_used="test",
    estimated_cost_usd=0.0,
)

# 6. Test file upload
print("\n=== Testing file upload ===")
try:
    file_id = adapter._upload_or_update_file(test_digest)
    if not file_id:
        sys.exit("[FAIL] _upload_or_update_file returned None")
    print(f"[OK]  File ID: {file_id}")
    print(f"[OK]  View at: https://drive.google.com/file/d/{file_id}/view")
except Exception as e:
    sys.exit(f"[FAIL] File upload failed: {e}")

# 7. Full publish_digest round-trip
print("\n=== Testing publish_digest round-trip ===")
success, result = adapter.publish_digest(test_digest)
if success:
    print(f"[OK]  publish_digest succeeded — file ID: {result}")
    print(f"\n✅  All checks passed. Drive upload is working.")
    print(f"    File: https://drive.google.com/file/d/{result}/view")
else:
    sys.exit(f"[FAIL] publish_digest failed: {result}")
