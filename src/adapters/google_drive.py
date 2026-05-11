"""Google Drive adapter for publishing digests"""

import io
import json
import os
import tempfile
import logging
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.auth.transport.requests import Request
from src.config import get_settings
from src.models.contracts import DigestOutput
from src.agents.publish_digest import DigestFormatterAgent

SCOPES = ["https://www.googleapis.com/auth/drive"]
logger = logging.getLogger(__name__)

# Paths (relative to project root, resolved at runtime)
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OAUTH_CLIENT_FILE = os.path.join(_BASE, "credentials", "google-oauth-client.json")
OAUTH_TOKEN_FILE = os.path.join(_BASE, "credentials", "google-oauth-token.json")


def _load_oauth_credentials(token_json: Optional[str] = None) -> OAuthCredentials:
    """Load OAuth user credentials from env JSON or local token file."""
    persist_path = None
    if token_json:
        try:
            token_data = json.loads(token_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid OAuth token JSON: {exc}") from exc
        creds = OAuthCredentials.from_authorized_user_info(token_data, SCOPES)
    else:
        if not os.path.exists(OAUTH_TOKEN_FILE):
            raise FileNotFoundError(
                f"OAuth token not found at {OAUTH_TOKEN_FILE}. "
                "Run `python setup_google_oauth.py` once to authorise."
            )
        creds = OAuthCredentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
        persist_path = OAUTH_TOKEN_FILE

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if persist_path:
            with open(persist_path, "w") as f:
                f.write(creds.to_json())
    return creds


def _load_service_account_credentials(json_str: str) -> ServiceAccountCredentials:
    """Load service account credentials from JSON string (no file writes).
    
    Args:
        json_str: Service account JSON as string (from env var)
        
    Returns:
        ServiceAccountCredentials: Credentials ready for Drive API use
        
    Raises:
        ValueError: If JSON is invalid
    """
    try:
        sa_config = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid service account JSON: {e}") from e
    
    creds = ServiceAccountCredentials.from_service_account_info(sa_config, scopes=SCOPES)
    return creds


class GoogleDriveAdapter:
    """Adapter for Google Drive API supporting both OAuth user credentials and service accounts.
    
    Auth precedence:
    1. If credentials_json is provided → use service account (Cloud Run mode)
    2. Otherwise use credentials_path → OAuth user credentials (local dev mode)
    """

    def __init__(
        self,
        credentials_path: str,
        folder_id: str,
        credentials_json: Optional[str] = None,
    ):
        self.settings = get_settings()
        self.credentials_path = credentials_path
        self.credentials_json = credentials_json
        self.folder_id = folder_id
        self.drive_service = None
        self.auth_method = None  # Tracking for logging/debugging
        self._initialize_service()

    def _initialize_service(self):
        """Initialize Google Drive service with conditional auth.
        
        Precedence:
        1. If credentials_json provided (Cloud Run via Secret Manager) → service account
        2. Otherwise (local dev) → OAuth user credentials
        """
        if self.credentials_json:
            # Cloud Run: Use service account from env var (no file persistence)
            try:
                creds = _load_service_account_credentials(self.credentials_json)
                self.auth_method = "service_account"
            except ValueError as e:
                raise ValueError(f"Failed to load service account credentials: {e}") from e
        else:
            # OAuth mode: Use token from env when provided, otherwise local token file.
            creds = _load_oauth_credentials(self.settings.google_oauth_token_json)
            self.auth_method = "oauth_user"
        
        self.drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def publish_digest(self, digest: DigestOutput) -> tuple[bool, str]:
        """Upload digest as a plain-text file directly into the shared Drive folder.

        Using a media upload means storage is attributed to the folder owner, not the
        service account — service accounts have no Drive storage quota of their own.

        Returns:
            tuple[bool, str]: (success, file_id_or_error)
        """
        try:
            if not self.drive_service:
                return (False, "Google Drive service is not initialized")

            file_id = self._upload_or_update_file(digest)
            if not file_id:
                return (False, "Upload returned no file ID")
            return (True, file_id)
        except HttpError as e:
            return (False, f"Google API error: {e}")
        except Exception as e:
            return (False, str(e))

    def _upload_or_update_file(self, digest: DigestOutput) -> Optional[str]:
        """Create or overwrite the daily digest file in the Drive folder."""
        filename, text, mime_type = self._digest_output_artifact(digest)
        media = self._build_media_upload(text, mime_type)

        # Check if file already exists so we can update in-place.
        safe_name = filename.replace("'", "\\'")
        query_parts = [f"name='{safe_name}'", "trashed=false"]
        if self.folder_id:
            query_parts.append(f"'{self.folder_id}' in parents")
        result = self.drive_service.files().list(
            q=" and ".join(query_parts),
            fields="files(id)",
            pageSize=1,
        ).execute()
        existing = result.get("files", [])

        if existing:
            file_id = existing[0]["id"]
            logger.info(
                "Drive upload branch=same_name_update filename=%s folder_id=%s file_id=%s",
                filename,
                self.folder_id or "<root>",
                file_id,
            )
            self.drive_service.files().update(
                fileId=file_id,
                media_body=media,
            ).execute()
            return file_id

        # Create new file directly inside the target folder.
        metadata: dict = {"name": filename}
        if self.folder_id:
            metadata["parents"] = [self.folder_id]
        try:
            logger.info(
                "Drive upload branch=create_new filename=%s folder_id=%s",
                filename,
                self.folder_id or "<root>",
            )
            created = self.drive_service.files().create(
                body=metadata,
                media_body=media,
                fields="id",
            ).execute()
            return created.get("id")
        except HttpError as exc:
            if not self._is_storage_quota_exceeded(exc):
                raise

            logger.error(
                "Drive upload branch=create_quota_failure filename=%s folder_id=%s: refusing rename fallback to protect history.",
                filename,
                self.folder_id or "<root>",
            )
            raise RuntimeError(
                "drive_storage_quota_exceeded: create failed and rename fallback disabled"
            ) from exc

    def _build_media_upload(self, content: bytes, mime_type: str) -> MediaIoBaseUpload:
        """Build a fresh media upload body."""
        return MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype=mime_type,
            resumable=False,
        )

    def _is_storage_quota_exceeded(self, err: HttpError) -> bool:
        """Check whether a Drive API error indicates storage quota exhaustion."""
        if getattr(err, "resp", None) is None:
            return False
        if getattr(err.resp, "status", None) != 403:
            return False
        content = getattr(err, "content", b"")
        if isinstance(content, bytes):
            content_text = content.decode("utf-8", errors="ignore")
        else:
            content_text = str(content)
        return "storageQuotaExceeded" in content_text

    def _digest_output_artifact(self, digest: DigestOutput) -> tuple[str, bytes, str]:
        """Build output artifact in priority order: PDF, then HTML, then markdown."""
        html = DigestFormatterAgent.digest_to_html(digest)

        # Attempt PDF-first output.
        try:
            from weasyprint import HTML

            pdf_bytes = HTML(string=html).write_pdf()
            return (
                f"Daily AI and Technology Digest - {digest.date}.pdf",
                pdf_bytes,
                "application/pdf",
            )
        except Exception as weasy_exc:
            logger.exception("WeasyPrint PDF render failed")
            # Try a browser-based PDF renderer as secondary option.
            try:
                from playwright.sync_api import sync_playwright

                with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tmp:
                    tmp.write(html)
                    html_path = tmp.name

                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(
                            args=["--no-sandbox", "--disable-dev-shm-usage"]
                        )
                        page = browser.new_page()
                        page.goto(f"file://{html_path}")
                        pdf_bytes = page.pdf(format="A4", print_background=True, margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"})
                        browser.close()

                    return (
                        f"Daily AI and Technology Digest - {digest.date}.pdf",
                        pdf_bytes,
                        "application/pdf",
                    )
                finally:
                    try:
                        os.remove(html_path)
                    except OSError:
                        pass
            except Exception as playwright_exc:
                logger.exception("Playwright PDF render failed")
                if self.settings.strict_pdf_only:
                    raise RuntimeError(
                        f"strict_pdf_render_failed: weasyprint={weasy_exc!r}; playwright={playwright_exc!r}"
                    ) from playwright_exc

                logger.warning(
                    "PDF rendering failed with both engines; falling back to non-PDF output",
                    exc_info=playwright_exc,
                )

            if self.settings.strict_pdf_only:
                raise RuntimeError(
                    f"strict_pdf_render_failed: weasyprint={weasy_exc!r}"
                ) from weasy_exc

            # Graceful fallback to HTML if PDF conversion is unavailable.
            try:
                return (
                    f"Daily AI and Technology Digest - {digest.date}.html",
                    html.encode("utf-8"),
                    "text/html",
                )
            except Exception:
                markdown = DigestFormatterAgent.digest_to_markdown(digest) + "\n"
                return (
                    f"Daily AI and Technology Digest - {digest.date}.md",
                    markdown.encode("utf-8"),
                    "text/markdown",
                )
