import sys
import os
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from services.script_generator import YouTubeUpload, YouTubeVideoSettings
from services.youtube_uploader import YouTubeUploader

# Sample JSON from User Request
SAMPLE_JSON = """
{
  "video_settings": {
    "category": "Film & Animation",
    "privacy": "public",
    "notify_subscribers": true,
    "embeddable": true,
    "license": "youtube",
    "made_for_kids": false
  },
  "titles": {
    "primary": "Lost in Dark Woods at Night \ud83d\ude31\ud83c\udf32 | Scary Animated Short (Part 1)",
    "alternatives": [
      "What's Hiding in the Dark Forest? \ud83d\udc40\ud83c\udf32 | Horror Animation",
      "NEVER Enter the Forest at Night... \ud83c\udf19\ud83d\udc79 | Horror Short"
    ]
  },
  "description": "A boy and his puppy get lost...",
  "tags": ["horror", "scary", "animation"],
  "thumbnail": {
    "text": "\ud83d\udd34\ud83d\udc41\ufe0f THEY'RE WATCHING \ud83d\udc41\ufe0f\ud83d\udd34",
    "elements": ["Boy's scared face", "Red glowing eyes"]
  },
  "engagement": {
    "pinned_comment": "Drop a \ud83d\ude31 if this gave you chills!",
    "reply_templates": {
      "part_2": "Part 2 coming soon!"
    }
  },
  "community_posts": {
    "pre_launch": {
      "timing": "24 hours before",
      "text": "New horror short dropping tomorrow!"
    }
  },
  "end_screen": {
    "duration_seconds": 10,
    "elements": [
      {
        "type": "subscribe",
        "position": "top_center",
        "start_time_seconds": 62,
        "end_time_seconds": 72
      }
    ]
  },
  "analytics_targets": {
    "first_24_hours": {
      "views": 1000,
      "ctr_percent": 5
    }
  }
}
"""

async def test_schema_validation():
    print("🧪 Testing Schema Validation...")
    try:
        data = json.loads(SAMPLE_JSON)
        model = YouTubeUpload(**data)
        print("✅ Pydantic Model Validated Successfully!")
        print(f"   Title: {model.titles.primary.encode('ascii', 'ignore').decode()}")
        print(f"   Privacy: {model.video_settings.privacy}")
        return model
    except Exception as e:
        print(f"❌ Schema Validation Failed: {e}")
        return None

async def test_uploader_flow(model):
    print("\n🧪 Testing Uploader Flow (Mocked)...")
    
    with patch('services.youtube_uploader.YouTubeUploader._load_credentials') as mock_creds, \
         patch('services.youtube_uploader.build') as mock_build:
        
        # Mock Uploader
        uploader = YouTubeUploader("pets")
        uploader.upload_private = MagicMock(return_value="VIDEO_123")
        uploader.set_thumbnail = MagicMock()
        uploader.promote_to_public = MagicMock()
        uploader.post_comment = MagicMock()
        # Mock internal helper methods we added
        uploader.add_end_screen = MagicMock() 
        
        # Run Enriched Upload
        result = await uploader.upload_enriched(
            video_path=Path("dummy.mp4"),
            youtube_upload_data=model.model_dump(),
            thumbnail_path=Path("thumb.jpg")
        )
        
        print("✅ Upload Enriched Call Completed")
        print(f"   Result: {result}")
        
        # Verify Calls
        uploader.upload_private.assert_called_once()
        uploader.set_thumbnail.assert_called_once()
        uploader.post_comment.assert_called_with("VIDEO_123", model.engagement.pinned_comment, pin=True)
        uploader.promote_to_public.assert_called_once_with("VIDEO_123")
        
        # Verify End Screen call (mocked internally)
        if model.end_screen:
            uploader.add_end_screen.assert_called_once()
        
        print("✅ All expected API calls were triggered (Mocked)")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        model = loop.run_until_complete(test_schema_validation())
        if model:
            loop.run_until_complete(test_uploader_flow(model))
    except Exception as e:
        print(f"❌ Test Failed: {e}")
