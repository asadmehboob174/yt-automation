
"""
Fal.ai Image Generator with Cloudflare Fallback.

Prioritizes Fal.ai for "Reference Consistency" using Flux IP-Adapters.
Falls back to Cloudflare Flux/SDXL if credits run out.
"""
import os
import logging
import fal_client
from typing import Optional

from .cloudflare_ai import CloudflareImageGenerator
from .usage_tracker import UsageTracker

logger = logging.getLogger(__name__)

class FalImageGenerator:
    """
    Primary Image Generator using Fal.ai Flux Pro/Dev.
    Supports usage tracking and Cloudflare fallback.
    """
    
    def __init__(self):
        self.fallback_generator = CloudflareImageGenerator()
        self.fal_key = os.getenv("FAL_KEY")
        
        if not self.fal_key:
            logger.warning("⚠️ FAL_KEY not found. Defaulting to Cloudflare for all generations.")
            
    async def generate(self, prompt: str, reference_image: Optional[str] = None, style_suffix: str = "") -> bytes:
        """
        Generate image using Fal.ai (Flux) with optional reference consistency.
        Checks for credit limit ($4.50) before running.
        Falls back to Cloudflare if limit reached or Fal fails.
        """
        # 1. Check Credit Limit
        spent = UsageTracker.get_total_spend()
        if spent >= 4.50:
            logger.warning(f"🛑 Fal.ai credit limit reached (${spent:.2f} >= $4.50). Switching to Cloudflare.")
            return await self._fallback(prompt, reference_image)

        if not self.fal_key:
            return await self._fallback(prompt, reference_image)

        try:
            full_prompt = f"{prompt}, {style_suffix}".strip()
            logger.info(f"🎨 Generating with Fal.ai Flux (Ref: {bool(reference_image)})")
            
            model_type = "schnell"

            if reference_image:
                model_type = "general"
                # Use Flux General with IP-Adapter for consistency
                handler = await fal_client.submit_async(
                    "fal-ai/flux-general",
                    arguments={
                        "prompt": full_prompt,
                        "image_url": reference_image,
                        "ip_adapter_scale": 0.8, # High consistency
                        "num_inference_steps": 28,
                        "guidance_scale": 3.5,
                        "enable_safety_checker": False
                    }
                )
            else:
                # Use Flux Schnell for fast, high-quality base images
                handler = await fal_client.submit_async(
                    "fal-ai/flux/schnell",
                    arguments={
                        "prompt": full_prompt,
                        "image_size": "landscape_16_9",
                        "num_inference_steps": 4,
                        "enable_safety_checker": False
                    }
                )

            # Wait for result
            result = await handler.get()
            
            # Track Usage only on success
            UsageTracker.track_generation(model_type)
            
            # Download result image
            image_url = result["images"][0]["url"]
            return await self._download_image(image_url)

        except Exception as e:
            logger.error(f"❌ Fal.ai failed: {e}. Falling back to Cloudflare.")
            return await self._fallback(prompt, reference_image)
            
    async def _fallback(self, prompt: str, reference_image: Optional[str] = None) -> bytes:
        """Helper to call fallback generator."""
        if reference_image:
             return await self.fallback_generator.generate_consistent_scene(prompt, reference_image)
        else:
             return await self.fallback_generator.generate_from_text(prompt)

    async def _download_image(self, url: str) -> bytes:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

# Compatibility wrapper to match PuLIDGenerator interface
class PuLIDGenerator(FalImageGenerator):
    """Naming compatibility alias for existing code."""
    pass
