
import asyncio
import os
from dotenv import load_dotenv
from packages.services.gemini_image_generator import GeminiImageGenerator

async def test_gemini():
    load_dotenv()
    print("🧪 Testing Gemini Image Generator...")
    
    try:
        gen = GeminiImageGenerator()
        
        # Test 1: Square (Character mode)
        print("📸 Generating 1:1 Square Image (Character mode)...")
        img_bytes = await gen.generate(
            prompt="A small delicate fairy with soft muted blue wings, Pixar 3D style",
            is_square=True
        )
        with open("test_character.png", "wb") as f:
            f.write(img_bytes)
        print(f"✅ Character image saved (Size: {len(img_bytes)} bytes)")
        
        # Test 2: Landscape (Scene mode)
        print("🌅 Generating 16:9 Landscape Image (Scene mode)...")
        img_bytes = await gen.generate(
            prompt="A magical forest with glowing flowers and a hidden waterfall, Pixar 3D style",
            is_shorts=False,
            is_square=False
        )
        with open("test_scene.png", "wb") as f:
            f.write(img_bytes)
        print(f"✅ Scene image saved (Size: {len(img_bytes)} bytes)")
        
        print("\n🎉 ALL TESTS PASSED!")
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gemini())
