
"""
Simple local usage tracker for Fal.ai credits.
Estimates spending based on generation counts.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TRACKER_FILE = Path("fal_usage.json")

# Estimated costs per generation (USD)
COST_SCHNELL = 0.003
COST_GENERAL_CONSISTENCY = 0.04  # Approximate for Pro/Dev + IP-Adapter

class UsageTracker:
    @staticmethod
    def get_total_spend() -> float:
        try:
            if not TRACKER_FILE.exists():
                return 0.0
            data = json.loads(TRACKER_FILE.read_text())
            return data.get("total_spend", 0.0)
        except Exception:
            return 0.0

    @staticmethod
    def track_generation(model_type: str):
        try:
            cost = COST_SCHNELL if model_type == "schnell" else COST_GENERAL_CONSISTENCY
            
            data = {"total_spend": 0.0}
            if TRACKER_FILE.exists():
                data = json.loads(TRACKER_FILE.read_text())
            
            data["total_spend"] = data.get("total_spend", 0.0) + cost
            TRACKER_FILE.write_text(json.dumps(data))
            
            logger.info(f"💰 Estimated Fal.ai Spend: ${data['total_spend']:.3f} (+${cost})")
        except Exception as e:
            logger.error(f"Failed to track usage: {e}")
