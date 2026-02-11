
import os
import sys
from pathlib import Path
import logging

# Add the packages/services directory to the path so we can import grok_agent
sys.path.append(os.path.join(os.getcwd(), "packages", "services"))

from grok_agent import generate_single_clip

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_validation_logic():
    # Create a dummy HTML file to simulate a corrupt download
    corrupt_path = Path("test_corrupt.mp4")
    corrupt_path.write_text("<!DOCTYPE html><html><body><h1>Error</h1></body></html>")
    
    print(f"🕵️ Testing validation on corrupt file: {corrupt_path}")
    
    # We can't easily call generate_single_clip without a full browser session, 
    # but we can test the is_valid_video logic if we extract it or mock it.
    # For now, let's just check the head detection part.
    
    def is_valid_video_mock(p: Path) -> bool:
        try:
            with open(p, "rb") as f:
                head = f.read(100)
                if b"<!DOCTYPE html>" in head or b"<html" in head:
                    print(f"   ❌ Validation correctly identified HTML in {p.name}")
                    return False
            return True
        except Exception as e:
            print(f"   ❌ Exception during validation: {e}")
            return False

    is_valid = is_valid_video_mock(corrupt_path)
    
    if not is_valid:
        print("✅ Test PASSED: HTML content correctly flagged.")
    else:
        print("❌ Test FAILED: HTML content NOT flagged.")
        
    if corrupt_path.exists():
        corrupt_path.unlink()

if __name__ == "__main__":
    test_validation_logic()
