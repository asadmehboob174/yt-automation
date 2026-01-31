import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.services.cloud_storage import R2Storage
from dotenv import load_dotenv

load_dotenv()

def nuke_videos():
    print("☢️  Nuking all videos in R2 (prefix: videos/)...")
    storage = R2Storage()
    
    # Passing -1 days ensures cutoff is in the future relative to file creation
    # effectively deleting EVERYTHING.
    # verify 'cleanup_uploaded_videos' exists and works as expected
    result = storage.cleanup_uploaded_videos(older_than_days=-1)
    
    print(f"✅ Deleted {result['deleted_count']} videos.")
    print(f"✅ Freed {result['freed_bytes'] / (1024**3):.2f} GB space.")

if __name__ == "__main__":
    nuke_videos()
