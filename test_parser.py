import sys
import os
import asyncio

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages"))
from services.script_generator import ScriptGenerator

test_script = """
🎞️ PART 3: SCENE-BY-SCENE STORYBOARD
SCENE 1 – The Printing Press 2.0

Shot Type: Close-up

Text-to-Image Prompt: A macro shot of a high-speed digital printing press spitting out crisp $100 bills, but the bills are dissolving into digital binary code (1s and 0s) as they move. [Artistic Influence: Cyberpunk 2077 meets Succession. Medium/Texture: High-end digital photography, 8k resolution, anamorphic lens flares, liquid metal textures. Color Palette: Electric blue, neon green (matrix-style), deep obsidian, and surgical white. Lighting/Environment: Neon-lit server rooms, rain-slicked glass skyscrapers, cold fluorescent office lights. Technical Keywords: Ray-tracing, volumetric digital fog, macro tech photography, motion-blurred cityscapes.]

Image-to-Video Prompt: The paper bills physically melt into glowing green digital fragments that float upward.

Audio: "Money isn't paper anymore. It’s just a line of code they can change at will."

SCENE 2 – The High-Frequency Trade

Shot Type: Wide Shot

Text-to-Image Prompt: A massive, dark server room with miles of glowing blue cables. Thousands of tiny red lights are blinking rapidly. [Artistic Influence: Cyberpunk 2077 meets Succession. Medium/Texture: High-end digital photography, 8k resolution, anamorphic lens flares, liquid metal textures. Color Palette: Electric blue, neon green (matrix-style), deep obsidian, and surgical white. Lighting/Environment: Neon-lit server rooms, rain-slicked glass skyscrapers, cold fluorescent office lights. Technical Keywords: Ray-tracing, volumetric digital fog, macro tech photography, motion-blurred cityscapes.]

Image-to-Video Prompt: Lights pulse faster and faster down the cables like a digital heartbeat.

Audio: "Billions of dollars move in milliseconds. Faster than a human can blink."
"""

async def run_test():
    gen = ScriptGenerator()
    try:
        result = gen.parse_manual_script(test_script)
        print(f"✅ Success! Found {len(result.scenes)} scenes.")
        if result.scenes:
            print(f"Scene 1 Prompt: {result.scenes[0].text_to_image_prompt}")
            print(f"Scene 1 Motion: {result.scenes[0].image_to_video_prompt}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
