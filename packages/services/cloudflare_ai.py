
"""
Cloudflare Workers AI Image Generator (Budget Efficient Version).

Uses Dreamshaper-8-LCM for high-speed, low-cost generations.
Optimized to consume minimal neurons while maintaining high aesthetic quality.
Includes a $3 hard-coded budget safeguard.
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
    """Generate images using Cloudflare Workers AI REST API with budget protection."""
    
    # Budget Model: Dreamshaper 8 (LCM) - Ultra fast and low neuron consumption
    TEXT_MODEL = "@cf/lykon/dreamshaper-8-lcm"
    
    # Budget Safeguard Constants
    FREE_DAILY_IMAGES = 50
    PAID_LIMIT_DOLLARS = 3.0
    NEURONS_PER_IMAGE = 200 # Conservative estimate for Dreamshaper 8 LCM (4 steps)
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
        """
        Verify if the current generation exceeds the configured budget.
        """
        usage = self._get_usage()
        paid_neurons = usage.get("paid_neurons", 0)
        
        # Load limit from env or default to 3.0
        try:
            limit_str = os.getenv("CF_BUDGET_LIMIT", "3.0")
            limit = float(limit_str)
        except:
            limit = self.PAID_LIMIT_DOLLARS

        # Calculate Current Spend
        current_spend = (paid_neurons / 1000) * self.COST_PER_1K_NEURONS
        
        if current_spend >= limit:
             error_msg = f"❌ Cloudflare Budget Exceeded (${current_spend:.2f} / ${limit:.2f}). Please check your Cloudflare Dashboard or increase CF_BUDGET_LIMIT in .env."
             logger.error(error_msg)
             raise RuntimeError(error_msg)
        
        logger.info(f"💰 Cloudflare Budget Check: ${current_spend:.2f} used. Limit: ${limit:.2f}. Safe to generate.")

    def _increment_usage(self):
        """Record a successful generation and update neuron count."""
        today = datetime.date.today().isoformat()
        usage = self._get_usage()
        
        daily_count = usage["daily"].get(today, 0)
        daily_count += 1
        usage["daily"][today] = daily_count
        
        # If we exceeded the free daily limit (50), start counting neurons towards budget
        if daily_count > self.FREE_DAILY_IMAGES:
            usage["paid_neurons"] = usage.get("paid_neurons", 0) + self.NEURONS_PER_IMAGE
            
        self._save_usage(usage)

    @staticmethod
    def _get_character_seed(name: str) -> int:
        """Deterministic seed from character name."""
        return abs(hash(name.strip().lower())) % (2 ** 31)

    @staticmethod
    def build_scene_prompt(scene_prompt: str, character_images: list, style_suffix: str = "") -> str:
        """Embed character descriptions into the scene prompt."""
        if not character_images:
            return scene_prompt
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
        """Generate image with budget safeguard."""
        # 🛡️ BUDGET CHECK
        self.check_budget()
        
        full_prompt = f"{prompt}, {style_suffix}, high quality, detailed, realistic".strip(", ")
        url = f"{self.base_url}/{self.TEXT_MODEL}"
        payload = {
            "prompt": full_prompt,
            "num_steps": 4, 
            "guidance": 1.0, 
        }
        if seed is not None:
             payload["seed"] = seed

        logger.info(f"🪙 Generating with Budget CF Dreamshaper (Steps: 4, {'Square' if is_square else 'Landscape'})...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                
                if response.status_code != 200:
                    logger.error(f"Cloudflare AI Error: {response.text}")
                    raise RuntimeError(f"Cloudflare AI request failed (Status {response.status_code})")
                
                result = response.content
                # Handle potential JSON wrapping
                try:
                    js = response.json()
                    if "result" in js and "image" in js["result"]:
                         result = base64.b64decode(js["result"]["image"])
                except:
                    pass
                
                # ✅ Record Success to Budget Tracker
                self._increment_usage()
                return result

        except Exception as e:
            logger.error(f"❌ Cloudflare (Budget) Image Generation failed: {e}")
            raise

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
        logger.info(f"💾 Budget character image saved locally: {local_path}")

        return image_bytes

# Compatibility wrapper
class PuLIDGenerator(CloudflareImageGenerator):
    pass
