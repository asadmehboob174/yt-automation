
import os
import httpx
import logging
import base64
import json
import asyncio
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class KaggleImageGenerator:
    """
    Image Generator using a Kaggle-hosted ComfyUI backend.
    
    This connects to a ComfyUI instance running on Kaggle via an Ngrok tunnel.
    Priority: Extreme (Free T4 GPU, high quality, consistent characters).
    """

    def __init__(self):
        self.ngrok_domain = os.getenv("KAGGLE_NGROK_DOMAIN")
        if not self.ngrok_domain:
            logger.error("❌ KAGGLE_NGROK_DOMAIN not set in .env")
            raise ValueError("KAGGLE_NGROK_DOMAIN is required for Kaggle Image Generation")
            
        # Ensure it starts with https://
        if not self.ngrok_domain.startswith("http"):
            self.api_url = f"https://{self.ngrok_domain}/generate"
        else:
            self.api_url = f"{self.ngrok_domain}/generate"
            
        logger.info(f"🏔️ Kaggle Image Generator initialized for: {self.api_url}")

    @staticmethod
    def _get_character_seed(name: str) -> int:
        """Deterministic seed for character consistency."""
        return abs(hash(name.strip().lower())) % (2 ** 31)

    @staticmethod
    def build_scene_prompt(scene_prompt: str, character_images: list, style_suffix: str = "") -> str:
        """
        Embed character descriptions into the prompt for visual consistency.
        Matches the interface used by Cloudflare and HuggingFace generators.
        """
        if not character_images:
            return scene_prompt

        prompt_lower = scene_prompt.lower()
        char_clauses = []

        for c in character_images:
            char_name = c.get("name", "")
            char_desc = c.get("prompt", "")
            if not char_name or not char_desc:
                continue

            # Parse aliases
            aliases = [alias.strip().lower() for alias in char_name.replace(" / ", "/").split("/")]

            # Only inject if mentioned
            if any(alias in prompt_lower for alias in aliases if len(alias) > 2):
                char_clauses.append(f"{char_name}: {char_desc}")

        if not char_clauses:
            return scene_prompt

        return f"{scene_prompt} — Characters: {'; '.join(char_clauses)}"

    async def upload_reference(self, image_data: bytes, index: int = 0) -> bool:
        """Upload a character reference image to the Kaggle server's /upload_reference endpoint."""
        upload_url = self.api_url.replace("/generate", "/upload_reference")
        # Ensure index is within standard triple-character limits (0, 1, or 2)
        target_index = min(max(0, index), 2)
        logger.info(f"📤 Uploading character reference #{target_index} to: {upload_url}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # v15.1 expects filed name 'image'
                files = {'image': (f'reference_{target_index}.png', image_data, 'image/png')}
                response = await client.post(
                    f"{upload_url}?index={target_index}", 
                    files=files,
                    headers={"ngrok-skip-browser-warning": "true"}
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Reference #{target_index} uploaded successfully.")
                    return True
                else:
                    logger.error(f"❌ Upload #{target_index} failed ({response.status_code}): {response.text}")
                    return False
        except Exception as e:
            logger.error(f"⚠️ Reference upload error: {e}")
            return False

    async def generate_character_image(
        self,
        name: str,
        prompt: str,
        niche_id: str,
        style_suffix: str = "",
        is_shorts: bool = False,
    ) -> bytes:
        """
        Generate a character reference image and save locally.
        Force square (1:1) to keep face features centered.
        """
        seed = self._get_character_seed(name)
        # For master portraits, we want 1:1 square
        image_bytes = await self.generate(
            prompt=prompt,
            style_suffix=style_suffix,
            seed=seed,
            is_shorts=is_shorts,
            is_square=True,
        )

        # Save locally for reference
        local_dir = Path("tmp") / "characters" / niche_id
        local_dir.mkdir(parents=True, exist_ok=True)
        safe_name = name.lower().replace(" / ", "_").replace("/", "_").replace(" ", "_").strip()
        local_path = local_dir / f"{safe_name}.png"
        local_path.write_bytes(image_bytes)
        logger.info(f"💾 Kaggle: Master character saved: {local_path}")

        return image_bytes

    async def generate(
        self,
        prompt: str,
        reference_images: Optional[list[str]] = None, # List of paths to local images
        style_suffix: str = "",
        seed: int = 42,
        is_shorts: bool = False,
        is_square: bool = False,
    ) -> bytes:
        """
        Primary generation call. Sends request to Kaggle via Ngrok.
        """
        from .kaggle_controller import kaggle_controller

        # 1. Self-healing: Ensure server is running before generating
        is_alive = await kaggle_controller.ensure_running()
        if not is_alive:
            logger.error("❌ Kaggle server is offline after restart attempts. Falling back.")
            raise RuntimeError("Kaggle server offline")

        # 2. Handle Reference Images (Dual IP-Adapter support)
        if reference_images and isinstance(reference_images, list):
            # 🧹 First, Clear old refs to ensure a clean slate
            clear_url = self.api_url.replace("/generate", "/clear_reference")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(clear_url, headers={"ngrok-skip-browser-warning": "true"})
            except: pass

            # Upload up to 3 references (Triple Character Synergy v15.0)
            for i, ref_path_str in enumerate(reference_images[:3]):
                ref_path = Path(ref_path_str)
                if ref_path.exists():
                    logger.info(f"🖼️ Using reference #{i}: {ref_path}")
                    img_data = ref_path.read_bytes()
                    await self.upload_reference(img_data, index=i)
        elif not reference_images:
            # 🧹 CLEAN SLATE: Tell Kaggle to clear the reference for landscape/general scenes
            try:
                clear_url = self.api_url.replace("/generate", "/clear_reference")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(clear_url, headers={"ngrok-skip-browser-warning": "true"})
                    logger.info("🧹 Reference cleared for clean landscape scene.")
            except Exception as e:
                logger.debug(f"⚠️ Failed to clear reference: {e}")

        # 3. Build the payload
        full_prompt = f"{prompt}, {style_suffix}, high quality, cinematic, realistic".strip(", ")
        
        # Format determines resolution
        if is_square:
            width, height = 1024, 1024
        elif is_shorts:
            width, height = 720, 1280
        else:
            width, height = 1280, 720

        payload = {
            "prompt": full_prompt,
            "seed": seed,
            "width": width,
            "height": height
        }

        logger.info(f"🚀 Sending Kaggle generation request: {width}x{height}, Seed: {seed}")

        # 4. Request logic
        MAX_RETRIES = 2
        for attempt in range(MAX_RETRIES):
            try:
                # ComfyUI is fast, but let's give it generous timeout for first load
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        self.api_url, 
                        json=payload,
                        headers={"ngrok-skip-browser-warning": "true"}
                    )
                    
                    if response.status_code == 200:
                        # Success! Response should be raw PNG bytes
                        return response.content
                    elif response.status_code == 503:
                        logger.warning(f"⏳ Kaggle server busy (503). Retrying in 10s...")
                        await asyncio.sleep(10)
                    else:
                        logger.error(f"❌ Kaggle API Error ({response.status_code}): {response.text}")
                        if attempt == MAX_RETRIES - 1:
                            raise RuntimeError(f"Kaggle request failed with status {response.status_code}")
                            
            except Exception as e:
                logger.error(f"⚠️ Kaggle generation attempt {attempt + 1} failed: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(5)

        raise RuntimeError("Kaggle generation failed after retries")

# Compatibility alias
class PuLIDGenerator(KaggleImageGenerator):
    pass
