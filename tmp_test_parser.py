import asyncio
from packages.services.script_generator import ScriptGenerator
import logging

logging.basicConfig(level=logging.INFO)

test_script = """
CHARACTER MASTER PROMPTS
1. Queen Fairy
Text-to-Image Prompt: A regal fairy queen

SCENE 12 — "The Queen Speaks"
Text-to-Image Prompt:
Medium close-up shot of Queen Fairy...
Image-to-Video Prompt:
Slow zoom into Queen Fairy's face...
Dialogue: "کل صبح نوجوان پریوں میں سے نئی ملکہ کا انتخاب کیا جائے گا۔ جو آسمانی دریا تک پہنچے گی، وہی اس گدی کی حق دار ہوگی۔"
Voiceover: no voiceover
"""

def main():
    sg = ScriptGenerator()
    result = sg.parse_manual_script(test_script)
    
    print("\n--- RESULTS ---")
    for s in result.scenes:
        print(f"Scene {s.scene_number} - {s.scene_title}")
        print(f"  Image Prompt  : {s.text_to_image_prompt.strip()}")
        print(f"  Video Prompt  : {s.image_to_video_prompt.strip()}")
        print(f"  Dialogue Field: {s.dialogue}")
        print(f"  Voiceover TTS : {s.voiceover_text}")

if __name__ == "__main__":
    main()
