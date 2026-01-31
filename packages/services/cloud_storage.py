"""
Cloud Storage Service - Cloudflare R2.

Handles uploading and downloading video clips to/from
Cloudflare R2 storage (S3-compatible).
"""
import os
import logging
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class R2Storage:
    """Upload and download clips to Cloudflare R2."""
    
    def __init__(self):
        self.endpoint = os.getenv("R2_ENDPOINT")
        self.bucket = os.getenv("R2_BUCKET", "video-clips")
        
        if not self.endpoint:
            raise ValueError("R2_ENDPOINT environment variable is required")
        
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )
    
    def upload(self, local_path: Path, remote_key: Optional[str] = None, content_type: str = "video/mp4") -> str:
        """Upload a file to R2 and return the remote key."""
        if remote_key is None:
            remote_key = f"clips/{local_path.name}"
        
        self.client.upload_file(
            str(local_path),
            self.bucket,
            remote_key,
            ExtraArgs={"ContentType": content_type}
        )
        
        logger.info(f"✅ Uploaded {local_path.name} to R2: {remote_key}")
        return remote_key

    def upload_asset(self, file_content: bytes, key: str, content_type: str) -> str:
        """Upload in-memory file content (e.g. from API upload)."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_content,
            ContentType=content_type,
        )
        return key
    
    def download(self, remote_key: str, local_path: Path) -> Path:
        """Download a file from R2."""
        self.client.download_file(self.bucket, remote_key, str(local_path))
        logger.info(f"✅ Downloaded {remote_key} from R2")
        return local_path
    
    def get_url(self, remote_key: str, expires_in: int = 3600) -> str:
        """
        Generate a URL for a file. 
        Prefers R2_PUBLIC_URL if set (faster, cacheable), otherwise Presigned S3 URL.
        """
        public_domain = os.getenv("R2_PUBLIC_URL") or os.getenv("CLOUDFLARE_PUBLIC_DOMAIN")
        
        if public_domain:
            # Remove trailing slash if present
            public_domain = public_domain.rstrip("/")
            # Ensure key doesn't have leading slash if domain has it (basic join safety)
            clean_key = remote_key.lstrip("/")
            return f"{public_domain}/{clean_key}"

        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": remote_key},
            ExpiresIn=expires_in,
        )
    
    def list_clips(self, prefix: str = "clips/") -> list[str]:
        """List all clips with a given prefix."""
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]
    
    # =========================================
    # FREE TIER MANAGEMENT (10GB limit on R2)
    # =========================================
    
    FREE_TIER_LIMIT_GB = 10
    CLEANUP_THRESHOLD_GB = 9  # Trigger cleanup when storage > 9GB
    
    def get_bucket_size(self) -> dict:
        """
        Get total bucket size and object count.
        
        Returns:
            dict with 'total_bytes', 'total_gb', 'object_count'
        """
        total_bytes = 0
        object_count = 0
        
        paginator = self.client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.bucket):
            for obj in page.get('Contents', []):
                total_bytes += obj['Size']
                object_count += 1
        
        total_gb = total_bytes / (1024 ** 3)
        
        logger.info(f"📊 Bucket size: {total_gb:.2f} GB ({object_count} objects)")
        
        return {
            'total_bytes': total_bytes,
            'total_gb': round(total_gb, 2),
            'object_count': object_count,
            'free_tier_remaining_gb': round(self.FREE_TIER_LIMIT_GB - total_gb, 2)
        }
    
    def list_objects_with_metadata(self, prefix: str = "") -> list[dict]:
        """
        List all objects with their metadata (key, size, last_modified).
        
        Returns:
            List of dicts with 'key', 'size_bytes', 'last_modified'
        """
        objects = []
        paginator = self.client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                objects.append({
                    'key': obj['Key'],
                    'size_bytes': obj['Size'],
                    'last_modified': obj['LastModified']
                })
        
        return objects
    
    def cleanup_old_clips(self, older_than_days: int = 7) -> dict:
        """
        Delete raw clips older than specified days.
        
        Args:
            older_than_days: Delete clips older than this many days
            
        Returns:
            dict with 'deleted_count', 'freed_bytes'
        """
        from datetime import datetime, timezone, timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        objects = self.list_objects_with_metadata(prefix="clips/")
        
        to_delete = [
            obj for obj in objects 
            if obj['last_modified'] < cutoff
        ]
        
        if not to_delete:
            logger.info("🧹 No old clips to delete")
            return {'deleted_count': 0, 'freed_bytes': 0}
        
        # Delete in batches of 1000 (S3 limit)
        deleted_count = 0
        freed_bytes = 0
        
        for i in range(0, len(to_delete), 1000):
            batch = to_delete[i:i+1000]
            delete_keys = [{'Key': obj['key']} for obj in batch]
            
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={'Objects': delete_keys}
            )
            
            deleted_count += len(batch)
            freed_bytes += sum(obj['size_bytes'] for obj in batch)
        
        freed_gb = freed_bytes / (1024 ** 3)
        logger.info(f"🧹 Deleted {deleted_count} old clips, freed {freed_gb:.2f} GB")
        
        return {'deleted_count': deleted_count, 'freed_bytes': freed_bytes}
    
    def cleanup_uploaded_videos(self, older_than_days: int = 30) -> dict:
        """
        Delete final rendered videos older than specified days.
        These are assumed to be uploaded to YouTube already.
        
        Args:
            older_than_days: Delete videos older than this many days
            
        Returns:
            dict with 'deleted_count', 'freed_bytes'
        """
        from datetime import datetime, timezone, timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        objects = self.list_objects_with_metadata(prefix="videos/")
        
        to_delete = [
            obj for obj in objects 
            if obj['last_modified'] < cutoff
        ]
        
        if not to_delete:
            logger.info("🧹 No old videos to delete")
            return {'deleted_count': 0, 'freed_bytes': 0}
        
        for i in range(0, len(to_delete), 1000):
            batch = to_delete[i:i+1000]
            delete_keys = [{'Key': obj['key']} for obj in batch]
            
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={'Objects': delete_keys}
            )
        
        deleted_count = len(to_delete)
        freed_bytes = sum(obj['size_bytes'] for obj in to_delete)
        freed_gb = freed_bytes / (1024 ** 3)
        
        logger.info(f"🧹 Deleted {deleted_count} old videos, freed {freed_gb:.2f} GB")
        
        return {'deleted_count': deleted_count, 'freed_bytes': freed_bytes}
    
    def ensure_storage_available(self, required_gb: float = 0.5) -> bool:
        """
        Check if there's enough storage, trigger cleanup if needed.
        
        Args:
            required_gb: How much space is needed for the upcoming operation
            
        Returns:
            True if space is available, False if cleanup couldn't free enough
        """
        stats = self.get_bucket_size()
        
        if stats['total_gb'] + required_gb > self.FREE_TIER_LIMIT_GB:
            logger.warning(f"⚠️ Storage near limit ({stats['total_gb']:.2f} GB), triggering cleanup...")
            
            # First try: cleanup old clips (7+ days)
            self.cleanup_old_clips(older_than_days=7)
            stats = self.get_bucket_size()
            
            if stats['total_gb'] + required_gb > self.FREE_TIER_LIMIT_GB:
                # Second try: cleanup old videos (30+ days)
                self.cleanup_uploaded_videos(older_than_days=30)
                stats = self.get_bucket_size()
            
            if stats['total_gb'] + required_gb > self.FREE_TIER_LIMIT_GB:
                # Third try: more aggressive clip cleanup (3+ days)
                self.cleanup_old_clips(older_than_days=3)
                stats = self.get_bucket_size()
        
        available = stats['total_gb'] + required_gb <= self.FREE_TIER_LIMIT_GB
        
        if available:
            logger.info(f"✅ Storage OK: {stats['free_tier_remaining_gb']:.2f} GB remaining")
        else:
            logger.error(f"❌ Not enough storage! {stats['total_gb']:.2f} GB used of {self.FREE_TIER_LIMIT_GB} GB")
        
        return available
    
    def delete_file(self, key: str) -> None:
        """Delete a single file from R2."""
        self.client.delete_object(Bucket=self.bucket, Key=key)
        logger.info(f"🗑️ Deleted: {key}")

