import asyncio
from packages.services.script_generator import ScriptGenerator
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

test_script = """
SCENE 12 — "The Queen Speaks"
Text-to-Image Prompt:
Medium close-up shot of Queen Fairy (Rani) sitting on her jeweled throne with regal authority, speaking with dignity, her golden crown glowing softly, magnificent silver-gold wings spread slightly outward, young fairies listening with reverent attention below her — Pixar 3D cartoon style, warm royal throne room lighting, 16:9
Image-to-Video Prompt:
Slow zoom into Queen Fairy's face as she speaks with calm authority. Her wings spread slightly wider with each word. The fairies before her listen in complete respectful silence. Golden chandelier light glows behind her crown.
Dialogue: "کل صبح نوجوان پریوں میں سے نئی ملکہ کا انتخاب کیا جائے گا۔ جو آسمانی دریا تک پہنچے گی، وہی اس گدی کی حق دار ہوگی۔"
Voiceover: no voiceover
"""

async def main():
    sg = ScriptGenerator()
    try:
        print("Testing HuggingFace LLM parser...")
        result = await sg.parse_manual_script_llm(test_script)
        print("\n--- HF RESULTS ---")
        for s in result.scenes:
            print(f"Scene {s.scene_number} - {s.scene_title}")
            print(f"  Video Prompt  : {s.image_to_video_prompt.strip()}")
            print(f"  Dialogue Field: {s.dialogue}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"HF Error Output: {e}")

    try:
        print("\nTesting Gemini LLM parser...")
        result2 = await sg.parse_manual_script_gemini(test_script)
        print("\n--- Gemini RESULTS ---")
        for s in result2.scenes:
            print(f"Scene {s.scene_number} - {s.scene_title}")
            print(f"  Video Prompt  : {s.image_to_video_prompt.strip()}")
            print(f"  Dialogue Field: {s.dialogue}")
    except Exception as e:
        print(f"Gemini Error Output: {e}")

if __name__ == "__main__":
    asyncio.run(main())
