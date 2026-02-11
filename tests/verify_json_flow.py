import sys
import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add packages to path
# We assume the script is run from project root, so 'tests/verify_json_flow.py'
# The packages dir is 'packages' in root.
sys.path.insert(0, str(Path.cwd() / "packages"))

from services.script_generator import ScriptGenerator
from services.music_generator import generate_music_with_ai

async def test_json_parsing():
    print("\n--- Testing JSON Script Parsing ---")
    json_input = """
    {
      "characters": [
        {"name": "Hero", "prompt": "A brave hero"}
      ],
      "scenes": [
        {
          "scene_number": 1,
          "text_to_image_prompt": "Hero standing",
          "grok_video_prompt": {
             "main_action": "Hero draws sword",
             "emotion": "determined",
             "camera_movement": "zoom in",
             "vfx": "particles",
             "lighting_changes": "dark to light",
             "character_animation": "smooth",
             "pacing": "fast",
             "full_prompt": null
          },
          "music_notes": "Epic orchestral swell",
          "sfx": ["sword_draw", "wind"]
        }
      ]
    }
    """
    generator = ScriptGenerator()
    result = generator.parse_json_script(json_input)
    
    print(f"Characters found: {len(result.characters)}")
    print(f"Scenes found: {len(result.scenes)}")
    if result.scenes:
        scene = result.scenes[0]
        
        # Check new fields
        grok = scene.grok_video_prompt
        if grok:
            print(f"Scene 1 Grok Action: {grok.main_action}")
            print(f"Scene 1 Grok VFX: {grok.vfx}")
        else:
            print("❌ Grok Prompt Missing")

        print(f"Scene 1 Music Notes: {scene.music_notes}")
        print(f"Scene 1 SFX: {scene.sfx}")
        
        assert len(result.characters) == 1
        assert grok.main_action == "Hero draws sword"
        assert scene.music_notes == "Epic orchestral swell"
        assert "sword_draw" in scene.sfx
        print("✅ JSON Parsing Verification Passed")
    else:
        print("❌ No scenes found")

async def test_music_generation():
    print("\n--- Testing AI Music Generation ---")
    # Check if API Key exists
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        print("⚠️ HUGGINGFACE_API_KEY not set in environment. Skipping live music generation test.")
        return

    prompt = "Test short audio check"
    print(f"Generating music for prompt: '{prompt}'")
    # Generate very short clip
    path = await generate_music_with_ai(prompt, duration=2)
    
    if path and path.exists():
        print(f"✅ Music Generated at: {path}")
        print(f"Size: {path.stat().st_size} bytes")
        # Cleanup
        try:
            path.unlink()
        except: pass
    else:
        print("❌ Music Generation Failed")

async def main():
    try:
        await test_json_parsing()
        await test_music_generation()
    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
