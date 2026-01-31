"""
ZeroGPU Quota Tracker for Hugging Face Pro Tier.

Monitors GPU usage to prevent batch operations from
crashing mid-video when quota runs out.
"""
import httpx
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class QuotaTracker:
    """
    Monitor ZeroGPU usage for Hugging Face Pro ($9/month).
    Prevents batch operations from crashing mid-video when quota runs out.
    """
    
    HF_API = "https://huggingface.co/api/quota"
    DAILY_LIMIT_SECONDS = 1500  # ~25 minutes of H200 GPU time
    
    def __init__(self):
        self.token = os.getenv("HF_TOKEN")
        if not self.token:
            raise ValueError("HF_TOKEN environment variable is required")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    async def get_remaining_seconds(self) -> int:
        """
        Fetch remaining ZeroGPU seconds for today.
        For Free Tier users, this might return 0 or fail. 
        In those cases, we assume 'Unlimited' (Shared Queue) access.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.HF_API, headers=self.headers)
                if resp.status_code != 200:
                    logger.info("Could not fetch quota (likely Free Tier). Assuming shared queue usage.")
                    return 999999  # Dummy value for "unlimited" shared queue

                data = resp.json()
                # If 'compute_seconds_used' isn't present, it might be a free account
                if "compute_seconds_used" not in data:
                    return 999999
                    
                used = data.get("compute_seconds_used", 0)
                limit = self.DAILY_LIMIT_SECONDS
                
                # If they have a higher limit (e.g. Enterprise), use that
                # But typically this API is for ZeroGPU spaces checks.
                # For Inference API, there is no hard "second" limit on free, just rate limits.
                
                return max(0, limit - used)
        except Exception as e:
            logger.warning(f"Failed to fetch quota: {e}. Assuming Free Tier/Shared Queue.")
            return 999999
    
    async def can_generate_batch(
        self,
        scene_count: int,
        avg_seconds_per_scene: int = 30
    ) -> bool:
        """Check if quota is sufficient for a batch of scenes."""
        remaining = await self.get_remaining_seconds()
        
        # If we are in "Free Tier Mode" (999999), always allow
        if remaining > 50000:
            return True
            
        required = scene_count * avg_seconds_per_scene
        if remaining < required:
            logger.warning(
                f"Insufficient quota: {remaining}s remaining, {required}s required for {scene_count} scenes"
            )
            return False
        return True
    
    async def get_status_display(self) -> dict:
        """Return data for dashboard display."""
        remaining = await self.get_remaining_seconds()
        return {
            "remaining_seconds": remaining,
            "remaining_minutes": remaining // 60,
            "percent_used": int((1 - remaining / self.DAILY_LIMIT_SECONDS) * 100),
            "can_generate_50_scenes": remaining >= 1500,  # 50 * 30s
            "warning": remaining < 300,  # Less than 5 minutes
        }
