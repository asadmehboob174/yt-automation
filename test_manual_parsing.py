
import asyncio
from packages.services.script_generator import ScriptGenerator

TEST_SCRIPT = """
🎨 CHARACTER MASTER PROMPTS (WITH CONSISTENT STYLE)
1. The Father

Text-to-Image Prompt:
A kind-faced father in his early 40s, Studio Ghibli style, short soft black hair, wearing round silver-rimmed glasses and a thick olive-green knit sweater. He has a gentle and patient expression.
Style: Authentic Studio Ghibli hand-painted aesthetic, soft watercolor and gouache textures with visible brushstrokes, thin organic linework, nostalgic muted color palette with earthy greens and warm ambers, cinematic soft lighting, gentle depth, cozy atmosphere, high-quality 2D anime illustration, visual consistency optimized for Google Whisk.

2. The Mother

Text-to-Image Prompt:
A serene mother in her late 30s, Studio Ghibli style, long chestnut brown hair tied in a loose side-braid. She wears a cream-colored linen apron over a soft floral-print dress. Her expression is warm and welcoming with amber-colored eyes.
Style: Authentic Studio Ghibli hand-painted aesthetic, soft watercolor and gouache textures with visible brushstrokes, thin organic linework, nostalgic muted color palette with warm creams and soft florals, cinematic gentle lighting, cozy domestic mood, high-quality 2D anime illustration, Google Whisk–consistent style.

🎞️ SCENE PROMPTS (STYLE APPLIED TO EACH)
🎞️ SCENE 1 – The Rainy Road

Shot: Wide Shot

Text-to-Image Prompt:
A cozy camper van driving down a winding road through a lush green forest, heavy rain falling, soft gray clouds, wet road reflecting light.
Style: Authentic Studio Ghibli hand-painted aesthetic, watercolor and gouache textures with visible brushstrokes, thin organic linework, muted rainy greens and cool grays, cinematic overcast lighting, komorebi diffused through clouds, detailed natural environment, high-quality 2D anime illustration, Google Whisk–consistent style.

Image-to-Video Prompt:
Rain falls steadily on the road as the van moves slowly through the trees.

Dialogue (Narrator):
“Sunday morning started with the sound of rain.”

🎞️ SCENE 2 – Sanctuary Inside

Shot: Medium Shot

Text-to-Image Prompt:
Interior of a cozy camper van with wooden furnishings, warm amber lighting, a family of three (father, mother, and young son) sitting close together, sense of safety and comfort.
Style: Authentic Studio Ghibli hand-painted aesthetic, soft watercolor and gouache textures, warm ambers and browns, thin organic linework, cozy interior lighting, nostalgic atmosphere, cinematic softness, Google Whisk–optimized consistency.

Image-to-Video Prompt:
The family looks out the window, cozy and warm.

Dialogue (Mom):
“It’s so peaceful in here.”
"""

def test():
    generator = ScriptGenerator()
    try:
        result = generator.parse_manual_script(TEST_SCRIPT)
        print("\n✅ Parsing Successful!")
        print(f"Characters Found: {len(result.characters)}")
        for i, char in enumerate(result.characters):
            print(f"  {i+1}. {char.name}")
            print(f"     Prompt: {char.prompt[:50]}...")
            
        print(f"\nScenes Found: {len(result.scenes)}")
        for i, scene in enumerate(result.scenes):
            print(f"  {i+1}. [Scene {scene.scene_number}] {scene.scene_title}")
            print(f"     Angle: {scene.camera_angle}")
            print(f"     Dialogue: {scene.dialogue}")
            print(f"     Full Prompt: {scene.character_pose_prompt[:50]}...")
            
    except Exception as e:
        print(f"❌ Parsing Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
