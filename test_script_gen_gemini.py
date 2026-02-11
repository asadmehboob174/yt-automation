import asyncio
import os
from dotenv import load_dotenv
from packages.services.script_generator import ScriptGenerator

load_dotenv()

async def main():
    print("Testing ScriptGenerator with Gemini 2.0 Flash (Robust)...")
    generator = ScriptGenerator()
    
    # Test 1: Generate a fresh script
    print("\n--- TEST 1: Generating Script ---")
    try:
        script = await generator.generate(
            topic="The Mystery of the Deep Ocean",
            niche_style="Documentary",
            scene_count=3
        )
        print("✅ Script Generated Successfully!")
        print(f"Title: {script.title}")
        print(f"Scenes: {len(script.scenes)}")
        print(f"First Scene Trace: {script.scenes[0].voiceover_text[:50]}...")
    except Exception as e:
        print(f"❌ Script Generation Failed: {e}")

    # Test 2: Parse Manual Script (Mock)
    print("\n--- TEST 2: Parsing Manual Script ---")
    mock_script = """
    PART 1
    
    SCENE 1
    Visual: A dark underwater canyon.
    Audio: Deep rumbling sounds.
    Voiceover: No one knew what lies beneath.
    
    SCENE 2
    Visual: A bright light appears.
    Audio: High pitched ping.
    Voiceover: Until now.
    """
    try:
        parsed = await generator.parse_manual_script_llm(mock_script)
        print("✅ Manual Script Parsed Successfully!")
        print(f"Scenes Found: {len(parsed.scenes)}")
        print(f"Scene 1 Visual: {parsed.scenes[0].text_to_image_prompt}")
    except Exception as e:
        print(f"❌ Manual Parsing Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
