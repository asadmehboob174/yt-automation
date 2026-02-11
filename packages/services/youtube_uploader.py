"""
YouTube Uploader with Private-to-Public Workflow.

Implements safe upload process:
1. Upload as PRIVATE
2. Wait 15 minutes for Content ID checks
3. Poll for copyright issues
4. Promote to PUBLIC only if clean
5. Include AI disclosure flag
"""
import os
import time
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube"]


@dataclass
class UploadResult:
    """Result of a YouTube upload operation."""
    video_id: str
    status: str  # "private", "unlisted", "public", "blocked"
    copyright_status: Optional[str] = None
    message: Optional[str] = None


class YouTubeUploader:
    """Upload videos with Private-to-Public copyright check workflow."""
    
    def __init__(self, niche_id: str):
        self.niche_id = niche_id
        self.credentials = self._load_credentials()
        self.youtube = build("youtube", "v3", credentials=self.credentials)
    
    def _load_credentials(self) -> Credentials:
        """Load OAuth credentials for the niche's YouTube channel."""
        token_path = Path(f"./secrets/{self.niche_id}_token.json")
        creds = None
        
        # Load existing token
        if token_path.exists():
            with open(token_path, "rb") as f:
                creds = pickle.load(f)
        
        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        
        # Create new credentials if needed
        if not creds or not creds.valid:
            print("🔑 YouTube: Starting new OAuth flow. This should open a browser window...")
            client_secrets = os.getenv("GOOGLE_CLIENT_SECRETS_PATH", "./secrets/client_secrets.json")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
            
            # Use console if browser fails or port=0
            try:
                creds = flow.run_local_server(port=0, timeout_seconds=120)
            except Exception as e:
                print(f"⚠️ YouTube: Browser auth failed ({e}). Falling back to console auth...")
                creds = flow.run_console()
            
            # Save for next time
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)
            print("✅ YouTube: Authentication successful.")
        
        return creds
    
    def upload_private(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        category_id: str = "22"  # People & Blogs
    ) -> str:
        """Upload video as PRIVATE with AI disclosure flag."""
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False,
                # AI Disclosure (YouTube 2026 requirement)
                "containsSyntheticMedia": True,
            },
        }
        
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=256 * 1024  # 256KB chunks
        )
        
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload progress: {int(status.progress() * 100)}%")
        
        video_id = response["id"]
        logger.info(f"✅ Uploaded as PRIVATE: {video_id}")
        return video_id
    
    def check_copyright_status(self, video_id: str) -> dict:
        """Check copyright status of an uploaded video."""
        response = self.youtube.videos().list(
            part="status,contentDetails",
            id=video_id
        ).execute()
        
        if not response.get("items"):
            return {"status": "not_found", "claims": []}
        
        video = response["items"][0]
        status = video.get("status", {})
        
        # Check for copyright claims
        content_details = video.get("contentDetails", {})
        claims = []
        
        # Check upload status
        upload_status = status.get("uploadStatus", "unknown")
        
        # Check for rejections or issues
        rejection_reason = status.get("rejectionReason")
        failure_reason = status.get("failureReason")
        
        return {
            "upload_status": upload_status,
            "rejection_reason": rejection_reason,
            "failure_reason": failure_reason,
            "claims": claims,
            "is_clean": upload_status == "processed" and not rejection_reason,
        }
    
    def promote_to_public(self, video_id: str):
        """Change video status from PRIVATE to PUBLIC."""
        self.youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {"privacyStatus": "public"},
            }
        ).execute()
        logger.info(f"✅ Promoted to PUBLIC: {video_id}")
    
    def promote_to_unlisted(self, video_id: str):
        """Change video status to UNLISTED (safer middle ground)."""
        self.youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {"privacyStatus": "unlisted"},
            }
        ).execute()
        logger.info(f"✅ Promoted to UNLISTED: {video_id}")
    
    def upload_with_copyright_check(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        wait_minutes: int = 15,
        promote_to: str = "unlisted"  # "public" or "unlisted"
    ) -> UploadResult:
        """
        Full Private-to-Public workflow:
        1. Upload as PRIVATE
        2. Wait for YouTube processing
        3. Check for copyright issues
        4. Promote only if clean
        """
        # Step 1: Upload as private
        video_id = self.upload_private(video_path, title, description, tags)
        
        # Step 2: Wait for processing
        print(f"⏳ YouTube: Waiting {wait_minutes} minutes for processing & copyright check...")
        for i in range(wait_minutes):
            print(f"   ... ({wait_minutes - i}m remaining)")
            time.sleep(60)
        
        # Step 3: Check copyright status
        print(f"🕵️ YouTube: Checking copyright status for {video_id}...")
        status = self.check_copyright_status(video_id)
        
        if not status["is_clean"]:
            logger.warning(f"⚠️ Video has issues: {status}")
            return UploadResult(
                video_id=video_id,
                status="blocked",
                copyright_status=status.get("rejection_reason"),
                message="Video has copyright or policy issues. Keeping PRIVATE."
            )
        
        # Step 4: Promote if clean
        if promote_to == "public":
            self.promote_to_public(video_id)
        else:
            self.promote_to_unlisted(video_id)
        
        return UploadResult(
            video_id=video_id,
            status=promote_to,
            message=f"Successfully uploaded and promoted to {promote_to}"
        )

    async def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_path: Optional[Path] = None,
        privacy_status: str = "private",
        category_id: str = "22"
    ) -> dict:
        """
        Unified upload method called by the workflow.
        Handles both video and optional thumbnail.
        """
        try:
            # 1. Upload video
            video_id = self.upload_private(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category_id=category_id
            )
            
            # 2. Upload thumbnail if exists
            if thumbnail_path and thumbnail_path.exists():
                self.set_thumbnail(video_id, thumbnail_path)
            
            # 3. Promote if requested (usually starts as private)
            if privacy_status != "private":
                if privacy_status == "public":
                    self.promote_to_public(video_id)
                elif privacy_status == "unlisted":
                    self.promote_to_unlisted(video_id)

            return {
                "video_id": video_id,
                "status": privacy_status,
                "url": f"https://youtu.be/{video_id}"
            }
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            raise

    def set_thumbnail(self, video_id: str, thumbnail_path: Path):
        """Upload a custom thumbnail for a video with retries and mimetype detection."""
        import mimetypes
        
        # Detect mimetype dynamically
        content_type, _ = mimetypes.guess_type(str(thumbnail_path))
        if not content_type:
            content_type = 'image/jpeg' # Fallback
            
        logger.info(f"🖼️ Uploading thumbnail for {video_id} from {thumbnail_path} (Mime: {content_type})")
        
        # Timing: Wait a bit for YouTube to register the video ID before attaching thumbnail
        # This is often needed for very fast uploads
        time.sleep(5)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_path), mimetype=content_type)
                ).execute()
                logger.info(f"✅ Thumbnail set successfully (Attempt {attempt + 1})")
                return
            except Exception as e:
                logger.warning(f"⚠️ Attempt {attempt + 1} to set thumbnail failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(10 * (attempt + 1)) # Exponential backoff
                else:
                    logger.error(f"❌ Failed to set thumbnail after {max_retries} attempts")

