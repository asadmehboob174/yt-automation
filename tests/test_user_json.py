
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

# Mock imports
sys.modules["services.inngest_client"] = MagicMock()
sys.modules["inngest"] = MagicMock()

from services.script_generator import ScriptGenerator

def test_user_json():
    json_text = """
{
  "project": {
    "title": "The Treehouse Standoff",
    "genre": "Adventure/Survival",
    "style": "Pixar-style 3D",
    "total_duration": "72s",
    "aspect_ratio": "9:16",
    "fps": 24
  },
  "global_settings": {
    "visual_style": "High-quality Pixar-style 3D render. Saturated forest colors early on, transitioning to a cinematic 'Golden Hour' sunset and a moody, atmospheric blue-black night. Realistic fur and cloth simulations.",
    "lighting": "Volumetric god-rays in the canopy, high-contrast rim lighting during the night, and warm indoor glow for the finale.",
    "camera_quality": "4K Cinematic, mix of sweeping wide shots, intense shaky-cam for the lion reveal, and intimate close-ups.",
    "environment": "Lush jungle with towering ancient trees, thick mossy bark, and bioluminescent forest elements at night."
  },
  "characters": [
    {
      "id": "BOY",
      "name": "Leo",
      "whisk_prompt": "A high-quality Pixar-style 3D 12-year-old boy. Messy dark hair, large expressive brown eyes, wearing a vibrant red hoodie and blue jeans. Face is capable of extreme joy and paralyzing fear. 4K render, realistic skin subsurface scattering.",
      "personality": "Adventurous, creative, and fiercely protective of his cat."
    },
    {
      "id": "CAT",
      "name": "Mochi",
      "whisk_prompt": "Adorable Pixar-style ginger tabby cat with big emerald eyes and fluffy, high-detail fur. Wears a small blue collar. Highly expressive ears and tail. Realistic fur grooming and physics.",
      "personality": "Curious, agile, but becomes a 'scaredy-cat' when the lion appears."
    },
    {
      "id": "LION",
      "name": "The King",
      "whisk_prompt": "Massive, powerful lion in Pixar’s stylized realism. Huge dark golden mane, piercing amber eyes, and heavy muscular frame. Looks majestic but terrifying. Every muscle twitch is visible under the fur.",
      "personality": "Patient, dominant, and intimidating predator."
    }
  ],
  "scenes": [
    {
      "scene_number": 1,
      "title": "The Adventure Begins",
      "duration": "6s",
      "grok_video_prompt": {
        "full_prompt": "[00:00–00:02] — Wide shot: Leo in his red hoodie and Mochi the ginger cat walk excitedly into a sun-drenched Pixar forest. [00:02–00:04] — Leo carries a stack of wooden boards, looking around with a huge smile. [00:04–00:06] — Mochi trots ahead, jumping playfully over a fallen mossy branch. High-quality 3D, god-rays. AUDIO: [LEO]: 'This is the perfect day for a treehouse, Mochi!' SFX: Birds chirping, cat meowing happily."
      }
    },
    {
      "scene_number": 2,
      "title": "The Giant Oak",
      "duration": "6s",
      "grok_video_prompt": {
        "full_prompt": "[00:00–00:02] — Low angle: The camera pans up a massive, ancient oak tree with thick, flat branches. [00:02–00:04] — Leo drops the wood boards at the base of the tree with a heavy thud. [00:04–00:06] — He wipes sweat from his forehead and looks up, determined to build. Pixar-style scale. SFX: Heavy wood thud, wind rustling the canopy."
      }
    }
  ],
  "final_assembly": {
    "total_clips": 12,
    "soundtrack": {
      "background_music": "Dynamic orchestral score: Whimsical (1-18s) → Silence/Suspense (18-24s) → Predatory Horror (24-54s) → Triumphant Relief (54-72s)",
      "sfx_mixing": "Make the lion's roar the loudest point; use heavy bass. Keep the cat's purring/meowing intimate."
    },
    "transitions": {
      "type": "Snappy cuts for building; slow dissolves for the sunset wait; whip-pan for the final run.",
      "duration": "0.2s"
    },
    "color_grading": {
      "overall_look": "Vibrant Pixar greens to high-contrast Golden Hour, finishing with warm amber indoor lighting."
    }
  },
  "youtube_upload": {
    "titles": {
      "primary": "Trapped by a LION in our Treehouse! 😱🦁 | Animated Adventure",
      "alternatives": [
        "My Cat vs. A Giant Lion?! 🐈💨🦁",
        "The Longest Night of our Lives... 😰🌳",
        "Never build a treehouse here! ❌🌲"
      ]
    },
    "description": "Description here...",
    "tags": ["lion vs cat", "treehouse story"],
    "engagement": {
      "pinned_comment": "🦁 THANK GOODNESS THEY MADE IT!"
    }
  }
}
"""
    print("Testing JSON Parsing...")
    data = json.loads(json_text)
    
    generator = ScriptGenerator()
    try:
        output = generator.parse_json_script(data)
        print("✅ Parsing Successful!")
        print(f"Characters: {len(output.characters)}")
        print(f"Scenes: {len(output.scenes)}")
        print(f"Assembly: {output.final_assembly is not None}")
        print(f"YouTube: {output.youtube_upload is not None}")
    except ValueError as e:
        print(f"❌ Parsing Failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    test_user_json()
