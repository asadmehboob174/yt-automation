
"""
Hugging Face Image Generator.

Uses Hugging Face Inference API for image generation.
Model: black-forest-labs/FLUX.1-schnell (Current SOTA open-source realism)
"""
import os
import logging
import httpx
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class HuggingFaceImageGenerator:
    """
    Image Generator using Hugging Face Inference API.
    """

    # FLUX.1 Schnell - Current SOTA for open-source realism
    MODEL_ID = "black-forest-labs/FLUX.1-schnell"

    def __init__(self):
        self.api_token = os.getenv("HF_TOKEN2") or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN")

        if not self.api_token:
            logger.error("❌ Missing HF_TOKEN. Image generation will fail.")
            raise ValueError("HF_TOKEN is required for Hugging Face Image Generation")

        self.api_url = f"https://router.huggingface.co/hf-inference/models/{self.MODEL_ID}"
        self.headers = {"Authorization": f"Bearer {self.api_token}"}

    @staticmethod
    def _get_character_seed(name: str) -> int:
        """Deterministic seed from character name. Same name always produces same face."""
        return abs(hash(name.strip().lower())) % (2 ** 31)

    @staticmethod
    def build_scene_prompt(scene_prompt: str, character_images: list, style_suffix: str = "") -> str:
        """
        Embed character descriptions into the scene prompt for visual consistency.
        Only injects a character's description if their name (or alias) is actually
        referenced in the scene prompt — prevents polluting shots where they don't appear.

        character_images entries should have 'name' and 'prompt' keys.
        Names with slashes are treated as aliases: "BLUE FAIRY / NEELI" → ["blue fairy", "neeli"]
        If 'prompt' is missing (old format with only imageUrl), falls back gracefully.
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

            # Parse aliases: "BLUE FAIRY / NEELI" → ["blue fairy", "neeli"]
            aliases = [alias.strip().lower() for alias in char_name.replace(" / ", "/").split("/")]

            # Only inject if this character is actually mentioned in the scene
            is_mentioned = any(alias in prompt_lower for alias in aliases if len(alias) > 2)
            if is_mentioned:
                char_clauses.append(f"{char_name}: {char_desc}")

        if not char_clauses:
            return scene_prompt

        return f"{scene_prompt} — Characters: {'; '.join(char_clauses)}"

    async def generate(
        self,
        prompt: str,
        reference_image: Optional[str] = None,
        style_suffix: str = "",
        seed: int = 42,
        is_shorts: bool = False,
        is_square: bool = False,
    ) -> bytes:
        """
        Generate image using Hugging Face API (Flux).
        Uses fixed seed for consistency.
        is_shorts=True → 9:16 portrait (720x1280), False → 16:9 landscape (1280x720).
        is_square=True → 1:1 square (1024x1024) - Best for characters.
        """
        full_prompt = f"{prompt}, {style_suffix}, hyper-realistic, 8k, cinematic lighting".strip(", ")

        if reference_image:
            logger.info("ℹ️ Reference image skipped (HF Free Tier limitation). Relying on seed/prompt.")

        if is_square:
            width, height = (1024, 1024)
        else:
            # Standard HD resolutions to prevent stretching (Flux works best with these buckets)
            width, height = (720, 1280) if is_shorts else (1280, 720)

        payload = {
            "inputs": full_prompt,
            "parameters": {
                "seed": seed,
                "width": width,
                "height": height,
            }
        }

        logger.info(f"🎨 Generating with HF Flux (Seed: {seed}, {'9:16' if is_shorts else '16:9'})...")

        return await self._make_request(payload)

    async def generate_character_image(
        self,
        name: str,
        prompt: str,
        niche_id: str,
        style_suffix: str = "",
        is_shorts: bool = False,
    ) -> bytes:
        """
        Generate a character image with a deterministic seed and save locally.
        Saves to tmp/characters/{niche_id}/{safe_name}.png for local reference.
        Returns raw image bytes.
        """
        seed = self._get_character_seed(name)
        image_bytes = await self.generate(
            prompt=prompt,
            style_suffix=style_suffix,
            seed=seed,
            is_shorts=is_shorts,
            is_square=True, # Force characters to be square to prevent Face stretching!
        )

        # Save locally for local reference
        local_dir = Path("tmp") / "characters" / niche_id
        local_dir.mkdir(parents=True, exist_ok=True)
        safe_name = name.lower().replace(" / ", "_").replace("/", "_").replace(" ", "_")
        local_path = local_dir / f"{safe_name}.png"
        local_path.write_bytes(image_bytes)
        logger.info(f"💾 Character image saved locally: {local_path}")

        return image_bytes

    async def _make_request(self, payload: dict) -> bytes:
        """Primary Generation via Pollinations AI (Flux)"""
        import urllib.parse
        import httpx
        import asyncio
        
        prompt = payload.get("inputs", "")
        params = payload.get("parameters", {})
        width = params.get("width", 1280)
        height = params.get("height", 720)
        seed = params.get("seed", 42)
        
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Explicitly use model=flux and standard bucket resolutions to avoid stretching
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true&enhance=false&model=flux"
        
        logger.info(f"🦸‍♂️ Generating with Pollinations AI (Flux): {width}x{height}, Seed: {seed}")
        
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                # 60s timeout is usually enough for Pollinations
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(url, follow_redirects=True)
                    if response.status_code == 200:
                        content_type = response.headers.get("content-type", "")
                        if "image" not in content_type.lower():
                            raise RuntimeError(f"Pollinations returned non-image: {content_type}")
                        logger.info("✅ Pollinations generation successful.")
                        return response.content
                    else:
                        logger.warning(f"Pollinations error ({response.status_code}): {response.text}")
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(5)
                            continue
            except Exception as e:
                logger.warning(f"Pollinations exception: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(5)
                    continue
        
        # FALLBACK to Hugging Face if Pollinations completely fails
        logger.warning("🔄 Pollinations failed. Falling back to Hugging Face API...")
        return await self._hf_fallback(payload)

    async def _hf_fallback(self, payload: dict) -> bytes:
        """Fallback to Hugging Face Inference API."""
        import asyncio
        import httpx
        
        MAX_RETRIES = 2
        BACKOFF = [10, 20]

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    logger.info(f"📡 HF fallback attempt {attempt + 1}/{MAX_RETRIES}...")
                    response = await client.post(self.api_url, headers=self.headers, json=payload)

                    if response.status_code == 503:
                        wait = BACKOFF[min(attempt, len(BACKOFF) - 1)]
                        logger.warning(f"⏳ HF model loading (503). Waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue

                    if response.status_code == 429:
                        wait = BACKOFF[min(attempt, len(BACKOFF) - 1)] * 2
                        logger.warning(f"⏳ HF rate limited (429). Waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue

                    if response.status_code != 200:
                        err_text = response.text
                        logger.error(f"Hugging Face API Error: {err_text}")
                        raise RuntimeError(f"HF request failed: {err_text}")

                    return response.content

            except httpx.TimeoutException:
                wait = BACKOFF[min(attempt, len(BACKOFF) - 1)]
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    raise RuntimeError("HF request timed out")

        raise RuntimeError("HF fallback failed after all retries")

# Compatibility wrapper to match expected interface
class PuLIDGenerator(HuggingFaceImageGenerator):
    """Naming compatibility alias."""
    pass
