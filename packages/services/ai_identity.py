"""
AI Identity Engine - PuLID-FLUX Character Consistency.

Generates images with consistent character identity using
Flux.1-dev + PuLID via Hugging Face API.
"""
import os
import httpx
import asyncio
import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PuLIDGenerator:
    """Generate consistent character images using PuLID-FLUX-v1 via Hugging Face API."""
    
    API_URL = "https://router.huggingface.co/hf-inference/models/InstantX/PuLID-FLUX-v1"
    
    def __init__(self):
        self.token = os.getenv("HF_TOKEN")
        if not self.token:
            raise ValueError("HF_TOKEN environment variable is required")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    async def generate(
        self,
        anchor_image_path: Path,
        prompt: str,
        style_suffix: str = ""
    ) -> bytes:
        """Generate image with consistent character identity."""
        # Read and encode anchor image
        with open(anchor_image_path, "rb") as f:
            anchor_b64 = base64.b64encode(f.read()).decode()
        
        # Combine prompt with style
        full_prompt = f"{prompt}. {style_suffix}" if style_suffix else prompt
        
        payload = {
            "inputs": full_prompt,
            "parameters": {
                "id_image": anchor_b64,
                "id_weight": 0.8,  # Balance identity vs prompt
                "num_steps": 30,
                "guidance_scale": 7.5,
            }
        }
        
        # Retry with exponential backoff
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        self.API_URL,
                        headers=self.headers,
                        json=payload
                    )
                    response.raise_for_status()
                    return response.content
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:  # Model loading
                    wait_time = 2 ** attempt
                    logger.info(f"Model loading, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        
        raise RuntimeError("Failed to generate image after 3 attempts")
    
    async def generate_scene(
        self,
        anchor_image_path: Path,
        character_pose: str,
        background: str,
        camera_angle: str,
        style_suffix: str
    ) -> bytes:
        """Generate a complete scene image."""
        prompt = f"{camera_angle} of {character_pose}. Background: {background}"
        return await self.generate(anchor_image_path, prompt, style_suffix)
    
    async def generate_from_text(self, prompt: str) -> bytes:
        """Generate image from text prompt only (no anchor image needed).
        
        Uses Stable Diffusion XL for high-quality character generation.
        """
        # Use SDXL for text-to-image generation
        sdxl_url = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "width": 1024,
                "height": 1024,
            }
        }
        
        # Retry with exponential backoff
        for attempt in range(5):
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    logger.info(f"🎨 Generating image from text (attempt {attempt+1})...")
                    response = await client.post(
                        sdxl_url,
                        headers=self.headers,
                        json=payload
                    )
                    
                    if response.status_code == 503:
                        # Model loading
                        data = response.json()
                        wait_time = data.get("estimated_time", 20)
                        logger.info(f"⏳ Model loading, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if response.status_code == 429:
                        # Rate limited
                        wait_time = 2 ** attempt
                        logger.info(f"⚠️ Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
                    return response.content
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text[:200]}")
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
            except Exception as e:
                logger.error(f"Error generating image: {e}")
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
        
        raise RuntimeError("Failed to generate image after 5 attempts")
