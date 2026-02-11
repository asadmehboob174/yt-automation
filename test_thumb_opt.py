import os
import sys
from pathlib import Path
from PIL import Image

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages"))

from services.youtube_seo import ThumbnailGenerator, ThumbnailConfig

def test_thumbnail_optimization():
    generator = ThumbnailGenerator()
    temp_dir = Path("./temp/test_thumbs")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Test 9:16 background (Shorts style)
    shorts_bg = temp_dir / "shorts_test.png"
    Image.new("RGB", (1080, 1920), color=(255, 0, 0)).save(shorts_bg)
    
    print("\n--- Testing 9:16 (Shorts) Background ---")
    out1 = generator.generate(
        background_image=shorts_bg,
        title_text="SHORTS TEST",
        output_path=temp_dir / "out_shorts.jpg"
    )
    img1 = Image.open(out1)
    print(f"Generated resolution: {img1.size} (Expected: 1280x720)")
    
    # 2. Test Large Image (Compression)
    # Create a very noisy/detailed image that might save large
    large_bg = temp_dir / "large_test.png"
    # Random noise to make it hard to compress
    import numpy as np
    noise = np.random.randint(0, 256, (2000, 2000, 3), dtype=np.uint8)
    Image.fromarray(noise).save(large_bg)
    
    print("\n--- Testing Compression (2MB Limit) ---")
    out2 = generator.generate(
        background_image=large_bg,
        title_text="COMPRESSION TEST",
        output_path=temp_dir / "out_large.jpg"
    )
    size_mb = os.path.getsize(out2) / (1024 * 1024)
    print(f"Final file size: {size_mb:.2f}MB (Limit: 2.00MB)")
    
    if size_mb <= 2.0:
        print("✅ SUCCESS: Thumbnail is under 2MB")
    else:
        print("❌ FAILURE: Thumbnail exceeds 2MB")

if __name__ == "__main__":
    test_thumbnail_optimization()
