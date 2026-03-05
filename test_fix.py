
import asyncio
import sys
import os

# Add packages to path
sys.path.insert(0, os.path.abspath("packages"))

from services.script_generator import ScriptGenerator
from services.script_generator import SceneBreakdown, TechnicalBreakdownOutput
import json

async def test():
    generator = ScriptGenerator()
    
    # 1. Test the cleanup method directly
    print("--- Test 1: Direct Cleanup Method ---")
    scenes = [
        SceneBreakdown(
            scene_number=1,
            voiceover_text="This is dialogue", # This is what we want to avoid
            voiceover="no voiceover",
            dialogue="This is dialogue"
        )
    ]
    breakdown = TechnicalBreakdownOutput(characters=[], scenes=scenes)
    cleaned = generator._cleanup_scenes_silence(breakdown)
    s = cleaned.scenes[0]
    print(f"Scene 1 Voiceover Text: [{s.voiceover_text}]")
    print(f"Scene 1 Dialogue: [{s.dialogue}]")
    
    assert s.voiceover_text == ""
    assert s.dialogue is None
    print("✅ Direct cleanup works!")

    # 2. Test the Regex Parser with a full script
    print("\n--- Test 2: Regex Parser with Full Script ---")
    script_text = """
PART 1: CHARACTER MASTER PROMPTS
[ZARA] — A young woman with a red umbrella.

PART 3: THE DETAILED SCENE BREAKDOWN
SCENE 1
Text-to-Image Prompt: Zara walking in rain.
Image-to-Video Prompt: She laughs. Dialogue: "Hello world"
Voiceover: no voiceover
"""
    
    breakdown = generator.parse_manual_script(script_text)
    print(f"Extracted {len(breakdown.scenes)} scenes.")
    
    if len(breakdown.scenes) > 0:
        s = breakdown.scenes[0]
        print(f"Scene {s.scene_number} Voiceover Text: [{s.voiceover_text}]")
        print(f"Scene {s.scene_number} Dialogue: [{s.dialogue}]")
        
        if s.voiceover_text == "" and (s.dialogue is None or s.dialogue == ""):
            print("✅ Regex Parser cleanup works!")
        else:
            print("❌ Regex Parser cleanup FAILED!")
            sys.exit(1)
    else:
        print("❌ FAILED: No scenes extracted via Regex Parser!")
        sys.exit(1)

    print("\n🎉 ALL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test())
