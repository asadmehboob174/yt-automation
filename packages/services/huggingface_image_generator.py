
"""
Hugging Face Image Generator.

Uses Hugging Face Inference API for image generation.
Model: stabilityai/stable-diffusion-xl-base-1.0 (High quality, widely available)
"""
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

class HuggingFaceImageGenerator:
    """
    Image Generator using Hugging Face Inference API.
    """
    
    # FLUX.1 Schnell - Current SOTA for open-source realism
    MODEL_ID = "black-forest-labs/FLUX.1-schnell"
    
    def __init__(self):
        self.api_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN")
        
        if not self.api_token:
            logger.error("❌ Missing HF_TOKEN. Image generation will fail.")
            raise ValueError("HF_TOKEN is required for Hugging Face Image Generation")
            
        self.api_url = f"https://api-inference.huggingface.co/models/{self.MODEL_ID}"
        self.headers = {"Authorization": f"Bearer {self.api_token}"}

    async def generate(self, prompt: str, reference_image: Optional[str] = None, style_suffix: str = "", seed: int = 42) -> bytes:
        """
        Generate image using Hugging Face API (Flux).
        Uses fixed seed for consistency.
        """
        
        # Combine prompt with style
        # FLUX follows complex prompts well, so we format it carefully
        full_prompt = f"{prompt}, {style_suffix}, hyper-realistic, 8k, cinematic lighting".strip()
        
        if reference_image:
             logger.info("ℹ️ Reference image skipped (HF Free Tier limitation). Relying on seed/prompt.")

        # Flux payload structure for HF Inference
        # Note: HF Inference API parameters can vary. 
        # For Flux, it is often just "inputs" string, but to pass seed we might need "parameters".
        
        payload = {
            "inputs": full_prompt,
            "parameters": {
                "seed": seed,
                # "num_inference_steps": 4, # Flux Schnell is optimized for few steps, often server-side fixed
                "width": 1024,
                "height": 576, # 16:9 Aspect Ratio
            }
        }
        
        logger.info(f"🎨 Generating with HF Flux (Seed: {seed})...")
        
        return await self._make_request(payload)

    async def _make_request(self, payload: dict) -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.api_url, headers=self.headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"Hugging Face API Error: {response.text}")
                raise RuntimeError(f"Hugging Face request failed: {response.text}")
                
            # HF Flux endpoint usually returns raw image bytes (JPEG/PNG)
            return response.content

# Compatibility wrapper to match expected interface
class PuLIDGenerator(HuggingFaceImageGenerator):
    """Naming compatibility alias."""
    pass
