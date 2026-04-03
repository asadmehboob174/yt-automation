
import os
import logging
from typing import Union, Optional
from .cloudflare_ai import CloudflareImageGenerator
from .gemini_image_generator import GeminiImageGenerator
from .huggingface_image_generator import HuggingFaceImageGenerator

logger = logging.getLogger(__name__)

def get_image_generator() -> Union[CloudflareImageGenerator, GeminiImageGenerator, HuggingFaceImageGenerator]:
    """
    Factory function to return the best available image generator.
    Priority: Cloudflare (Flux-1-Schnell) -> Gemini (Pro Plan) -> Hugging Face (Credits/Pollinations).
    """
    cf_token = os.getenv("CF_API_TOKEN") or os.getenv("CLOUDFLARE_API_TOKEN")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    # ⚡ 1st Choice: Cloudflare Workers AI (Flux-1-Schnell)
    if cf_token:
        try:
            logger.info("🌤️ Attempting to use Cloudflare Workers AI Image Generator (Flux)...")
            return CloudflareImageGenerator()
        except Exception as e:
            logger.warning(f"⚠️ Cloudflare Generator initialization failed: {e}. Falling back...")

    # 💎 2nd Choice: Gemini (Imagen 3)
    if gemini_key:
        try:
            logger.info("💎 Attempting to use Gemini Image Generator (Imagen 3)...")
            return GeminiImageGenerator()
        except Exception as e:
            logger.warning(f"⚠️ Gemini Generator initialization failed: {e}. Falling back...")
    
    # 🌊 3rd Choice: Hugging Face / Pollinations
    logger.info("🌊 Using Hugging Face Image Generator (HF/Pollinations)...")
    return HuggingFaceImageGenerator()
