"""Drive upload agent"""

import logging
import os
from datetime import datetime
from typing import Optional
from src.agents.base_agent import BaseAgent
from src.models.contracts import AgentMessage, DigestOutput, RunContext
from src.adapters.google_drive import GoogleDriveAdapter
from src.config import get_settings

logger = logging.getLogger(__name__)


class DriveUploadAgent(BaseAgent):
    """Uploads digest to Google Drive"""

    def __init__(self):
        """Initialize Drive upload agent"""
        super().__init__("drive_uploader")
        self.settings = get_settings()
        self.drive_adapter: Optional[GoogleDriveAdapter] = None

    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        """Upload digest to Google Drive
        
        Args:
            context: Run context
            input_data: Should contain 'digest' dict
            
        Returns:
            AgentMessage: Result with document URL or fallback info
        """
        msg = self.create_message(context, "upload_digest_drive")
        
        try:
            digest_data = input_data.get("digest", {})
            digest = DigestOutput(**digest_data)
            
            # Initialize Drive adapter with conditional auth
            # Cloud Run: service account JSON from Secret Manager (env var)
            # Local dev: OAuth credentials from file
            sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            if sa_json:
                # Cloud Run: use service account (no file required)
                self.drive_adapter = GoogleDriveAdapter(
                    credentials_path="",  # unused in SA mode
                    folder_id=self.settings.google_drive_folder_id or "",
                    credentials_json=sa_json
                )
            elif os.path.exists(self.settings.google_application_credentials):
                # Local dev with OAuth: fall back to file-based credentials
                self.drive_adapter = GoogleDriveAdapter(
                    credentials_path=self.settings.google_application_credentials,
                    folder_id=self.settings.google_drive_folder_id or ""
                )
            
            if self.drive_adapter:
                # Log which auth method is being used (helpful for debugging)
                logger.info(f"Using {self.drive_adapter.auth_method} auth for Drive upload")
                
                success, doc_id = self.drive_adapter.publish_digest(digest)
                
                if success:
                    doc_url = f"https://drive.google.com/file/d/{doc_id}/view"
                    return msg.with_success(
                        payload={"document_id": doc_id, "document_url": doc_url},
                        metadata={"uploaded": True}
                    )
                return self._fallback_local_save(msg, digest, error=doc_id)
            
            # Fallback: save locally
            return self._fallback_local_save(msg, digest)
            
        except Exception as e:
            return self._fallback_local_save(msg, None, error=str(e))

    def _fallback_local_save(self, msg: AgentMessage, digest: Optional[DigestOutput] = None, error: str = None) -> AgentMessage:
        """Fallback to local file save when Drive upload fails
        
        Args:
            msg: Agent message to return
            digest: Digest to save
            error: Error message
            
        Returns:
            AgentMessage: Result with local fallback info
        """
        try:
            from src.agents.publish_digest import DigestFormatterAgent
            
            os.makedirs(self.settings.data_dir, exist_ok=True)
            
            if digest:
                # Save as markdown + styled HTML for local readability
                md_content = DigestFormatterAgent.digest_to_markdown(digest)
                html_content = DigestFormatterAgent.digest_to_html(digest)
                today = datetime.utcnow().strftime("%Y-%m-%d")
                md_file = os.path.join(self.settings.data_dir, f"digest_{today}.md")
                html_file = os.path.join(self.settings.data_dir, f"digest_{today}.html")
                pdf_file = os.path.join(self.settings.data_dir, f"digest_{today}.pdf")
                
                with open(md_file, "w") as f:
                    f.write(md_content)
                with open(html_file, "w") as f:
                    f.write(html_content)

                pdf_generated = False
                try:
                    from weasyprint import HTML

                    HTML(string=html_content).write_pdf(pdf_file)
                    pdf_generated = True
                except Exception:
                    pass
                
                return msg.with_success(
                    payload={
                        "local_file": md_file,
                        "local_html": html_file,
                        "local_pdf": pdf_file if pdf_generated else None,
                        "fallback": True,
                    },
                    metadata={
                        "saved_locally": True,
                        "pdf_generated": pdf_generated,
                        "reason": error or "Drive unavailable",
                    }
                )
        except:
            pass
        
        return msg.with_error(f"Upload failed and fallback save failed: {error}")
