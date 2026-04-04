import asyncio
import httpx
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_live_generation():
    print("\n🏔️  --- KAGGLE LIVE TEST INITIATED ---")
    
    try:
        from packages.services.image_generator_factory import get_image_generator
        from packages.services.kaggle_image_generator import KaggleImageGenerator
        
        generator = get_image_generator()
        
        if not isinstance(generator, KaggleImageGenerator):
            print(f"❌ Error: Factory returned '{type(generator).__name__}', but we expected 'KaggleImageGenerator'.")
            print("Check KAGGLE_NGROK_DOMAIN in your .env file.")
            return

        print(f"✅ Factory confirmed: Using {generator.api_url}")
        
        # Test Prompt
        prompt = "A majestic robotic eagle soaring over a futuristic crystal mountain, volumetric lighting, 8k, cinematic architecture"
        print(f"🎨 Sending test prompt: '{prompt}'...")
        
        # We'll use Shorts (9:16) format to test the most complex aspect ratio
        print(f"🎬 Sending Kaggle generation request: 720x1280 (300s timeout)...")
        
        # Increase timeout for the first warm-up run
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Check health first
            h_res = await client.get(
                f"https://{generator.ngrok_domain}/health",
                headers={"ngrok-skip-browser-warning": "true"}
            )
            print(f"🏥 Health Status: {h_res.status_code} - {h_res.text}")
            
            response = await client.post(
                generator.api_url, 
                json={
                    "prompt": prompt,
                    "is_shorts": True,
                    "seed": 42
                },
                headers={"ngrok-skip-browser-warning": "true"}
            )
            
            if response.status_code == 200:
                image_bytes = response.content
            else:
                raise RuntimeError(f"Kaggle API Error ({response.status_code}): {response.text}")
        
        # Save output
        output_path = Path("tests/kaggle_test_result.png")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)
        
        print(f"📖 SUCCESS! Image generated and saved to: {output_path.absolute()}")
        print(f"📏 File Size: {len(image_bytes) / 1024:.2f} KB")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
    except Exception as e:
        print(f"❌ Critical Test Failure: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_live_generation())
