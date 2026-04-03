
import asyncio
import os
from dotenv import load_dotenv
from packages.services.cloudflare_ai import CloudflareImageGenerator

async def test_cloudflare():
    load_dotenv()
    print("🧪 Testing Cloudflare Worker AI Generator...")
    
    try:
        gen = CloudflareImageGenerator()
        
        print("📸 Generating Test Image via Cloudflare Flux...")
        img_bytes = await gen.generate("A futuristic cyberpunk city at night with neon lights, 8k, cinematic")
        
        with open("test_cf_image.png", "wb") as f:
            f.write(img_bytes)
        
        print(f"✅ Cloudflare image saved (Size: {len(img_bytes)} bytes)")
        print("\n🎉 CLOUDFLARE TEST PASSED!")
        
    except Exception as e:
        print(f"❌ CLOUDFLARE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_cloudflare())
