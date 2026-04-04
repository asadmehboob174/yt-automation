
"""
Cloudflare Workers AI Image Generator (High-Quality Pro Version).

Uses Flux-1-Schnell for state-of-the-art realism and prompt adherence.
Optimized for high-quality video production with a $3 budget safeguard.
"""
import os
import httpx
import logging
import base64
import json
import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class CloudflareImageGenerator:
    """Generate images using Cloudflare Workers AI with Flux 1 Schnell."""
    
    # High-Quality Model: Flux 1 Schnell
    TEXT_MODEL = "@cf/black-forest-labs/flux-1-schnell"
    
    # Budget Safeguard Constants
    FREE_DAILY_IMAGES = 55 # Approx 10,000 / 180 neurons
    PAID_LIMIT_DOLLARS = 3.0
    NEURONS_PER_IMAGE = 180 # Conservative estimate for Flux 1 Schnell (4 steps)
    COST_PER_1K_NEURONS = 0.011
    USAGE_FILE = Path("tmp") / "cf_usage.json"

    def __init__(self):
        # Extract Account ID from R2 URL if not provided directly
        self.account_id = os.getenv("CF_ACCOUNT_ID")
        r2_endpoint = os.getenv("R2_ENDPOINT", "")
        
        if not self.account_id and "r2.cloudflarestorage.com" in r2_endpoint:
            try:
                self.account_id = r2_endpoint.split("https://")[1].split(".")[0]
            except Exception as e:
                logger.error(f"Failed to extract Account ID from R2 endpoint: {e}")
        
        self.api_token = os.getenv("CF_API_TOKEN") or os.getenv("CLOUDFLARE_API_TOKEN")
        
        if not self.account_id or not self.api_token:
            logger.error(f"❌ Missing CF_ACCOUNT_ID or CF_API_TOKEN.")
            raise ValueError("Cloudflare Account ID and API Token are required.")
            
        self.headers = {"Authorization": f"Bearer {self.api_token}"}
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run"

    def _get_usage(self):
        """Read usage from local file."""
        if not self.USAGE_FILE.exists():
            return {"daily": {}, "paid_neurons": 0}
        try:
            return json.loads(self.USAGE_FILE.read_text())
        except:
            return {"daily": {}, "paid_neurons": 0}

    def _save_usage(self, usage):
        """Save usage to local file."""
        self.USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.USAGE_FILE.write_text(json.dumps(usage, indent=2))

    def check_budget(self):
        """Verify if budget is exceeded."""
        usage = self._get_usage()
        paid_neurons = usage.get("paid_neurons", 0)
        
        try:
            limit_str = os.getenv("CF_BUDGET_LIMIT", "3.0")
            limit = float(limit_str)
        except:
            limit = self.PAID_LIMIT_DOLLARS

        current_spend = (paid_neurons / 1000) * self.COST_PER_1K_NEURONS
        
        if current_spend >= limit:
             error_msg = f"❌ Cloudflare Budget Exceeded (${current_spend:.2f} / ${limit:.2f}). Please increase CF_BUDGET_LIMIT in .env."
             logger.error(error_msg)
             raise RuntimeError(error_msg)
        
        logger.info(f"💰 Cloudflare Budget Check: ${current_spend:.2f} used. Limit: ${limit:.2f}. Safe to generate.")

    def _increment_usage(self):
        """Record successful generation."""
        today = datetime.date.today().isoformat()
        usage = self._get_usage()
        daily_count = usage["daily"].get(today, 0)
        daily_count += 1
        usage["daily"][today] = daily_count
        if daily_count > self.FREE_DAILY_IMAGES:
            usage["paid_neurons"] = usage.get("paid_neurons", 0) + self.NEURONS_PER_IMAGE
        self._save_usage(usage)

    @staticmethod
    def _get_character_seed(name: str) -> int:
        """Deterministic seed for character consistency."""
        return abs(hash(name.strip().lower())) % (2 ** 31)

    @staticmethod
    def build_scene_prompt(scene_prompt: str, character_images: list, style_suffix: str = "") -> str:
        """Embed character descriptions into prompt."""
        if not character_images: return scene_prompt
        prompt_lower = scene_prompt.lower()
        char_clauses = []
        for c in character_images:
            char_name = c.get("name", "")
            char_desc = c.get("prompt", "")
            if not char_name or not char_desc: continue
            aliases = [alias.strip().lower() for alias in char_name.replace(" / ", "/").split("/")]
            if any(alias in prompt_lower for alias in aliases if len(alias) > 2):
                char_clauses.append(f"{char_name}: {char_desc}")
        if not char_clauses: return scene_prompt
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
        """Generate high-quality image with budget safeguard.
        
        Note: Cloudflare Flux-1-Schnell only supports 'prompt' and 'steps' params.
        It always generates a default square image (~1024x1024).
        We crop/resize the output to the correct aspect ratio after generation.
        """
        self.check_budget()
        
        # Flux Schnell is a next-gen model and prefers simple, descriptive prompts
        full_prompt = f"{prompt}, {style_suffix}, ultra-realistic, 8k, cinematic, extremely detailed".strip(", ")
        url = f"{self.base_url}/{self.TEXT_MODEL}"
        payload = {
            "prompt": full_prompt,
            "num_steps": 4, 
        }
        if seed is not None:
             payload["seed"] = seed

        # Determine target dimensions for post-processing
        if is_square:
            target_w, target_h = 1024, 1024
            ar_label = "Square 1:1"
        elif is_shorts:
            target_w, target_h = 720, 1280
            ar_label = "Portrait 9:16"
        else:
            target_w, target_h = 1280, 720
            ar_label = "Landscape 16:9"

        logger.info(f"✨ Generating with High-Quality Cloudflare Flux ({ar_label})...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"Cloudflare AI Error: {response.text}")
                    raise RuntimeError(f"Cloudflare AI request failed (Status {response.status_code})")
                
                js = response.json()
                if "result" in js and "image" in js["result"]:
                     raw_bytes = base64.b64decode(js["result"]["image"])
                     self._increment_usage()
                     
                     # Post-process: Crop/resize to target aspect ratio
                     if not is_square:
                         raw_bytes = self._crop_to_aspect(raw_bytes, target_w, target_h)
                     
                     return raw_bytes
                raise RuntimeError("Failed to extract image from Cloudflare response.")

        except Exception as e:
            logger.error(f"❌ Cloudflare (Pro) Image Generation failed: {e}")
            raise

    @staticmethod
    def _crop_to_aspect(image_bytes: bytes, target_w: int, target_h: int) -> bytes:
        """Crop and resize image to target aspect ratio.
        
        Cloudflare always returns a square image. This center-crops it to the 
        desired aspect ratio (e.g. 16:9 or 9:16) and resizes to target dimensions.
        """
        from PIL import Image
        import io
        
        img = Image.open(io.BytesIO(image_bytes))
        src_w, src_h = img.size
        
        # Calculate crop dimensions that preserve the target aspect ratio
        target_ratio = target_w / target_h
        src_ratio = src_w / src_h
        
        if src_ratio > target_ratio:
            # Source is wider than target -> crop width (center)
            new_w = int(src_h * target_ratio)
            new_h = src_h
            left = (src_w - new_w) // 2
            top = 0
        else:
            # Source is taller than target -> crop height (center)
            new_w = src_w
            new_h = int(src_w / target_ratio)
            left = 0
            top = (src_h - new_h) // 2
        
        # Center crop
        img = img.crop((left, top, left + new_w, top + new_h))
        
        # Resize to exact target dimensions
        img = img.resize((target_w, target_h), Image.LANCZOS)
        
        # Export as PNG
        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        
        logger.info(f"📐 Cropped {src_w}x{src_h} -> {target_w}x{target_h}")
        return buf.getvalue()

    async def generate_character_image(
        self,
        name: str,
        prompt: str,
        niche_id: str,
        style_suffix: str = "",
        is_shorts: bool = False,
    ) -> bytes:
        """Generate a character image with budget safeguard."""
        seed = self._get_character_seed(name)
        image_bytes = await self.generate(
            prompt=prompt,
            style_suffix=style_suffix,
            seed=seed,
            is_shorts=is_shorts,
            is_square=True,
        )
        local_dir = Path("tmp") / "characters" / niche_id
        local_dir.mkdir(parents=True, exist_ok=True)
        safe_name = name.lower().replace(" / ", "_").replace("/", "_").replace(" ", "_")
        local_path = local_dir / f"{safe_name}.png"
        local_path.write_bytes(image_bytes)
        logger.info(f"💾 High-quality character saved locally: {local_path}")
        return image_bytes

# Compatibility wrapper
class PuLIDGenerator(CloudflareImageGenerator):
    pass
