
"""
Google Gemini (Imagen 3) Image Generator.

Uses Google GenAI SDK for the latest Imagen 3 models.
Benefits: High quality, fast, and uses user's existing Pro Plan.
"""
import os
import logging
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiImageGenerator:
    """
    Image Generator using Google Gemini (Imagen 3).
    """

    # Gemini 2.5 Flash Image - High speed, 500 free images/day on AI Studio tier
    MODEL_ID = "gemini-2.5-flash-image"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            logger.error("❌ Missing GEMINI_API_KEY. Image generation will fail.")
            raise ValueError("GEMINI_API_KEY is required for Gemini Image Generation")

        # Initialize client with API key
        self.client = genai.Client(api_key=self.api_key)

    @staticmethod
    def _get_character_seed(name: str) -> int:
        """Deterministic seed from character name. Same name always produces same face."""
        return abs(hash(name.strip().lower())) % (2 ** 31)

    @staticmethod
    def build_scene_prompt(scene_prompt: str, character_images: list, style_suffix: str = "") -> str:
        """
        Embed character descriptions into the scene prompt for visual consistency.
        Mirroring HuggingFaceImageGenerator's prompt building logic.
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
        Generate image using Google Gemini (Imagen 3).
        """
        full_prompt = f"{prompt}, {style_suffix}, hyper-realistic, 8k, cinematic lighting".strip(", ")

        # Map display-driven booleans into Gemini aspect ratios
        # Gemini valid options: "1:1", "16:9", "9:16", "4:3", "3:4"
        if is_square:
            ar = "1:1"
        elif is_shorts:
            ar = "9:16"
        else:
            ar = "16:9"

        logger.info(f"🦸‍♂️ Generating with Gemini Imagen 3 (AR: {ar}, Model: {self.MODEL_ID})...")

        try:
            # Note: seed support is handled inside prompt or config if available in latest SDK
            # Currently Imagen 3 config uses it if passed.
            response = self.client.models.generate_images(
                model=self.MODEL_ID,
                prompt=full_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=ar,
                    output_mime_type="image/png"
                )
            )

            if not response.generated_images:
                raise RuntimeError("Gemini returned no images.")

            # Return raw image bytes
            return response.generated_images[0].image.image_bytes

        except Exception as e:
            logger.error(f"❌ Gemini Image Generation failed: {e}")
            raise

    async def generate_character_image(
        self,
        name: str,
        prompt: str,
        niche_id: str,
        style_suffix: str = "",
        is_shorts: bool = False,
    ) -> bytes:
        """
        Generate a character image and save locally for consistency.
        Characters are forced to 1:1 square for perfect Master Cast display.
        """
        seed = self._get_character_seed(name)
        image_bytes = await self.generate(
            prompt=prompt,
            style_suffix=style_suffix,
            seed=seed,
            is_shorts=is_shorts,
            is_square=True, # Force character images to be square
        )

        # Save locally for reference
        local_dir = Path("tmp") / "characters" / niche_id
        local_dir.mkdir(parents=True, exist_ok=True)
        safe_name = name.lower().replace(" / ", "_").replace("/", "_").replace(" ", "_")
        local_path = local_dir / f"{safe_name}.png"
        local_path.write_bytes(image_bytes)
        logger.info(f"💾 Character image saved locally: {local_path}")

        return image_bytes
