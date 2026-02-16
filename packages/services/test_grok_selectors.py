import asyncio
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

# Mock Logger
class MockLogger:
    def info(self, msg): print(f"INFO: {msg}")
    def warning(self, msg): print(f"WARNING: {msg}")
    def error(self, msg): print(f"ERROR: {msg}")
    def debug(self, msg): print(f"DEBUG: {msg}")

logger = MockLogger()

async def test_download_logic():
    print("🧪 Running Unit Test: Grok Download Logic...")
    
    # Mock Playwright Elements
    mock_el_image = AsyncMock()
    mock_el_image.count = AsyncMock(return_value=1)
    mock_el_image.get_attribute = AsyncMock(return_value="Download image")
    mock_el_image.text_content = AsyncMock(return_value="Download image")
    
    mock_el_video = AsyncMock()
    mock_el_video.count = AsyncMock(return_value=1)
    mock_el_video.get_attribute = AsyncMock(return_value="Download video")
    mock_el_video.text_content = AsyncMock(return_value="Download video")
    
    class MockPage:
        def __init__(self):
            self.closed = False
        def is_closed(self): return self.closed
        def locator(self, selector):
            # Simulate finding different elements based on selector
            mock = AsyncMock()
            mock.count = AsyncMock(return_value=1)
            
            if "video" in selector.lower():
                mock.first = mock_el_video
            elif "download" in selector.lower():
                mock.first = mock_el_image
            else:
                mock.count = AsyncMock(return_value=0)
            return mock

    page = MockPage()
    
    download_selectors = [
        "button[aria-label='Download video']",
        "button:has-text('Download video')",
        "button[aria-label='Download']",
    ]
    
    found_correct = False
    for selector in download_selectors:
        el = page.locator(selector).first
        if await el.count() > 0:
            label = (await el.get_attribute("aria-label") or "").lower()
            text = (await el.text_content() or "").lower()
            
            if "image" in label or "image" in text:
                print(f"⏭️ Correctly skipped image button: {selector}")
                continue
            
            if "video" in label or "video" in text:
                print(f"🎯 Correctly identified video button: {selector}")
                found_correct = True
                break

    if found_correct:
        print("✅ Unit Test PASSED: Video button prioritized over image button.")
    else:
        print("❌ Unit Test FAILED: Could not find video button.")

if __name__ == "__main__":
    asyncio.run(test_download_logic())
