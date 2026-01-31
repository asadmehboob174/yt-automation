"""
Cloudflare Workers AI Image Generator.

Replaces Hugging Face for faster, more consistent image generation
using Cloudflare's serverless AI models.
"""
import os
import httpx
import logging
import base64
from pathlib import Path

logger = logging.getLogger(__name__)

class CloudflareImageGenerator:
    """Generate images using Cloudflare Workers AI REST API."""
    
    # Text-to-Image Model (SDXL - Higher Quality for initial character)
    TEXT_MODEL = "@cf/stabilityai/stable-diffusion-xl-base-1.0"
    
    # Image-to-Image Model (SD 1.5 Img2Img - Better for consistency with reference)
    # Note: As of early 2026, creating consistent characters often uses 
    # specific adapters, but img2img with strong guidance is the standard "free" consistent method.
    IMG2IMG_MODEL = "@cf/runwayml/stable-diffusion-v1-5-img2img"

    def __init__(self):
        # Force load dotenv to ensure variables are present if called from script
        from dotenv import load_dotenv
        load_dotenv()
        
        # Extract Account ID from R2 URL if not provided directly
        self.account_id = os.getenv("CF_ACCOUNT_ID")
        
        # Debugging credentials (redacted)
        r2_endpoint = os.getenv("R2_ENDPOINT", "")
        # logger.info(f"debug: R2_ENDPOINT found: {bool(r2_endpoint)}")
        
        if not self.account_id:
            if "r2.cloudflarestorage.com" in r2_endpoint:
                try:
                    # Parse: https://<account_id>.r2.cloudflarestorage.com
                    self.account_id = r2_endpoint.split("https://")[1].split(".")[0]
                    # logger.info(f"debug: Extracted Account ID: {self.account_id[:4]}...")
                except Exception as e:
                    logger.error(f"Failed to extract Account ID from R2 endpoint: {e}")
            else:
                logger.warning(f"R2_ENDPOINT format not recognized for extraction: {r2_endpoint}")
        
        self.api_token = os.getenv("CF_API_TOKEN") or os.getenv("CLOUDFLARE_API_TOKEN")
        
        if not self.account_id:
             logger.error("MISSING: CF_ACCOUNT_ID (could not extract from R2_ENDPOINT)")
        if not self.api_token:
             logger.error("MISSING: CF_API_TOKEN (env var not found)")

        if not self.account_id or not self.api_token:
            raise ValueError(f"Cloudflare Account ID and API Token are required. (Acc={bool(self.account_id)}, Token={bool(self.api_token)})")
            
        self.headers = {"Authorization": f"Bearer {self.api_token}"}
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run"

    async def generate_from_text(self, prompt: str) -> bytes:
        """Generate high-quality character image from text (SDXL)."""
        url = f"{self.base_url}/{self.TEXT_MODEL}"
        
        payload = {
            "prompt": prompt,
            "num_steps": 20,
            "height": 1024,
            "width": 1024
        }
        
        return await self._make_request(url, payload)

    async def generate_consistent_scene(self, prompt: str, reference_image_url: str) -> bytes:
        """
        Generate a scene using a reference image for consistency.
        Uses Cloudflare's img2img capability.
        """
        # For img2img on Cloudflare, we usually pass the image as an array of integers 
        # OR as a signed URL if the model supports it.
        # However, checking Cloudflare docs, standard REST input for img2img expects:
        # { "prompt": "...", "image": [...binary data...] } or sometimes valid URL.
        # But many CF models prefer direct binary or integer array.
        
        # Strategy: Download the reference image from R2 first (using known URL)
        # Then send it to the AI model.
        
        logger.info(f"⬇️ Downloading reference image from {reference_image_url}...")
        image_bytes = await self._download_image(reference_image_url)
        
        # Convert bytes to list of integers (standard CF AI input format for images)
        # OR just rely on CF handling base64/buffer if using python client, 
        # but here we are using REST. 
        # The standard stable-diffusion-v1-5-img2img model on CF often accepts 
        # `image`: [ ... ] (array of uint8).
        
        # Let's try sending the bytes directly if httpx supports it, otherwise convert.
        # Actually, standard CF examples often show: "image": [binary_data]
        image_data = list(image_bytes)
        
        url = f"{self.base_url}/{self.IMG2IMG_MODEL}"
        
        payload = {
            "prompt": prompt,
            "image": image_data, # Pass image as array of integers
            "strength": 0.75, # Balanced: 0.75 matches script/prompt composition better while keeping colors
            "guidance": 7.5,
            "num_steps": 20
        }
        
        return await self._make_request(url, payload)

    async def _download_image(self, url: str) -> bytes:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def _make_request(self, url: str, payload: dict) -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=self.headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"Cloudflare AI Error: {response.text}")
                raise RuntimeError(f"Cloudflare AI request failed: {response.text}")
                
            # Response is usually the raw image bytes (PNG)
            return response.content

# Compatibility wrapper to match PuLIDGenerator interface
class PuLIDGenerator(CloudflareImageGenerator):
    """Naming compatibility alias for existing code."""
    pass
