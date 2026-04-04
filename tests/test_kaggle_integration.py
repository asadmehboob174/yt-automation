
import os
import asyncio
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_factory():
    # Load environment
    load_dotenv()
    
    from packages.services.image_generator_factory import get_image_generator
    from packages.services.kaggle_image_generator import KaggleImageGenerator
    
    print("\n🔍 Testing Image Generator Factory...")
    generator = get_image_generator()
    
    print(f"✅ Factory returned: {type(generator).__name__}")
    
    if isinstance(generator, KaggleImageGenerator):
        print("🏆 SUCCESS: Kaggle is now the #1 priority generator!")
        print(f"📡 API URL: {generator.api_url}")
    else:
        print("❌ FAILURE: Kaggle was not selected. Check your .env file.")

if __name__ == "__main__":
    asyncio.run(test_factory())
