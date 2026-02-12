import sys
import os
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from services.script_generator import FinalAssembly, ScriptGenerator, TechnicalBreakdownOutput

# Sample JSON including Final Assembly
SAMPLE_JSON_WITH_ASSEMBLY = """
{
  "characters": [],
  "scenes": [],
  "youtube_upload": {
      "video_settings": {"category": "Film & Animation", "privacy": "private"},
      "titles": {"primary": "Test", "alternatives": []},
      "description": "desc",
      "tags": ["tag"],
      "thumbnail": {"text": "txt", "elements": []}
  },
  "final_assembly": {
    "total_clips": 12,
    "soundtrack": {
      "background_music": "Dark orchestral horror score",
      "music_timing": "Adventure (1-3) -> Horror (7-9)",
      "sfx_mixing": "Layer SFX authentically"
    },
    "transitions": {
      "type": "Mix of quick cuts",
      "duration": "0.1s quick cuts",
      "effects": "Abrupt hard cut"
    },
    "color_grading": {
      "overall_look": "Desaturated horror",
      "consistency": "Dark stormy"
    },
    "title_cards": {
      "opening": "LOST IN THE DARK",
      "closing": "TO BE CONTINUED"
    },
    "youtube_optimization": {
      "format": "9:16",
      "hook": "Scene 1 grab attention",
      "pacing": "Fast",
      "ending": "Cliffhanger"
    }
  }
}
"""

def test_final_assembly_schema():
    print("🧪 Testing Final Assembly Schema Parsing...")
    try:
        generator = ScriptGenerator()
        # Mock _clean_json_text to return input as is for this test
        generator._clean_json_text = lambda x: x
        
        # Test parsing
        result = generator.parse_json_script(SAMPLE_JSON_WITH_ASSEMBLY)
        
        print("✅ JSON Parsed Successfully!")
        
        assert result.final_assembly is not None, "Final Assembly object is None"
        print("✅ Final Assembly object exists")
        
        fa = result.final_assembly
        print(f"   Soundtrack: {fa.soundtrack.background_music}")
        print(f"   Grading: {fa.color_grading.overall_look}")
        print(f"   Title Config: {fa.title_cards.opening}")
        
        assert fa.soundtrack.music_timing == "Adventure (1-3) -> Horror (7-9)"
        assert fa.title_cards.closing == "TO BE CONTINUED"
        
        print("✅ All fields verified correctly.")
        return True
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_final_assembly_schema()
