
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add packages to path
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "packages"))

# Load env vars
load_dotenv(".env")

from services.script_generator import ScriptGenerator

TEST_CASES = {
    "Manual Tab Simple (Regex)": """
    [LUNA] - cat
    
    SCENE 1:
    Text-to-Image: Close-up of Luna looking up...
    Text-to-Video: Luna slowly tilts her head...
    Dialogue: "Where am I?"
    Camera: Close-up
    
    SCENE 2:
    Text-to-Image: Luna explores...
    Dialogue: "It's so bright!"
    """
}

async def test_script_parsing():
    print("🚀 Starting Script Extraction Verification...")
    
    # --- Test 1: Gemini Extraction (New) ---
    print("\n✨ Testing Gemini Extraction...")
    try:
        # We need to manually inject the key if not loaded, but load_dotenv should handle it.
        # Assuming GEMINI_API_KEY is in .env or user provided it.
        gen = ScriptGenerator()
        if not gen.gemini_key:
             print("⚠️ Skipping Gemini test: GEMINI_API_KEY not found in environment.")
        else:
             breakdown = await gen.parse_manual_script_gemini(TEST_CASES["Manual Tab Simple (Regex)"])
             print(f"✅ Gemini Extraction Successful!")
             print(f"Scenes: {len(breakdown.scenes)}")
             print(f"Characters: {len(breakdown.characters)}")
    except Exception as e:
        print(f"❌ Gemini Extraction Failed: {e}")

    # --- Test 2: Regex Fallback (Indented Scenes) ---
    print("\n📝 Testing Regex Fallback (Indented Scenes)...")
    try:
        gen = ScriptGenerator()
        breakdown = gen.parse_manual_script(TEST_CASES["Manual Tab Simple (Regex)"])
        
        # We expect 2 scenes
        if len(breakdown.scenes) == 2:
            print(f"✅ Regex Fix Verified! Found {len(breakdown.scenes)} scenes.")
            for i, scene in enumerate(breakdown.scenes):
                print(f"-- Scene {i+1} --")
                print(f"  Img: {scene.text_to_image_prompt[:30]}...")
                print(f"  Dia: {scene.dialogue}")
        else:
             print(f"❌ Regex Fix Failed! Found {len(breakdown.scenes)} scenes (Expected 2).")
             
    except Exception as e:
        print(f"❌ Regex Fallback Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_script_parsing())
