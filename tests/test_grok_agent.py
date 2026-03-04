import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock
from pathlib import Path

from packages.services.grok_agent import generate_single_clip, VideoSettings, PromptBuilder, GrokAnimator

@pytest.mark.asyncio
async def test_prompt_builder_basic():
    """Verify prompt builder respects the negative text and dialogue."""
    prompt = PromptBuilder.build(
        character_pose="",
        camera_angle="Wide",
        style_suffix="",
        motion_description="Man walking.",
        dialogue="Hello world",
        sfx=["wind"]
    )
    assert "Shot: Wide" in prompt
    assert "Man walking." in prompt
    assert "Clean video, no text overlay, no subtitles" in prompt
    assert prompt.startswith("10s:")

@pytest.mark.asyncio
@patch("packages.services.grok_agent.VideoSettings.verify_clip_duration", return_value=True)
@patch("packages.services.grok_agent.check_rate_limit", return_value=False)
@patch("packages.services.grok_agent.VideoSettings.configure", new_callable=AsyncMock)
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_generate_single_clip_dialogue_mode(
    mock_sleep,
    mock_configure, 
    mock_check_rate_limit, 
    mock_verify,
    tmp_path,
    monkeypatch
):
    """Test two-pass flow for dialogue_mode."""
    
    class FastForwardTime:
        def __init__(self):
            self.t = 0
        def time(self):
            return self.t
            
    mock_timer = FastForwardTime()
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(loop, 'time', mock_timer.time)
    
    # Fast-forward time on every sleep
    async def fast_sleep(seconds):
        mock_timer.t += seconds
    mock_sleep.side_effect = fast_sleep

    # Mock Page
    page = MagicMock()
    page.url = "https://grok.com/imagine"
    page.is_closed = MagicMock(return_value=False)
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock()
    
    locators = {}
    
    def locator_side_effect(selector):
        if selector in locators:
            return locators[selector]
            
        m = MagicMock()
        m.count = AsyncMock(return_value=1)
        m.click = AsyncMock()
        m.fill = AsyncMock()
        
        # Generation indicators should be visible briefly
        gen_keywords = ["generating", "thinking", "progressbar", "pulse", "spin", "cancel"]
        if any(x in selector.lower() for x in gen_keywords):
            # Show for 2 calls per selector
            m.is_visible = AsyncMock(side_effect=[True, True, False, False, False, False, False])
        else:
            # All other requested elements are visible
            m.is_visible = AsyncMock(return_value=True)
        
        m.first = m
        locators[selector] = m
        return m
        
    page.locator.side_effect = locator_side_effect
    
    # Mock evaluate for video readiness
    async def mock_evaluate(js_code):
        if "Make video" in js_code:
            return True
        elif "querySelector('video')" in js_code:
            return {"ready": True, "duration": 10, "src": "blob:http://..."}
        return False
    page.evaluate.side_effect = mock_evaluate
    
    # Mock download logic
    mock_download = AsyncMock()
    async def mock_save_as(path):
        with open(path, "wb") as f: f.write(b"video data" * 20000)
    mock_download.save_as.side_effect = mock_save_as
    
    # Mock expect_download context manager
    dl_info = MagicMock()
    # Playwright's download info value is a coroutine that returns the Download object
    dl_info.value = AsyncMock(return_value=mock_download)
    
    class MockDownloadContext:
        async def __aenter__(self): return dl_info
        async def __aexit__(self, *args): pass
    page.expect_download.return_value = MockDownloadContext()

    # Mock file chooser
    fc_info = MagicMock()
    fc_info.value = AsyncMock()
    class MockFCContext:
        async def __aenter__(self): return fc_info
        async def __aexit__(self, *args): pass
    page.expect_file_chooser.return_value = MockFCContext()
    
    img_path = tmp_path / "test.png"
    img_path.touch()
    
    with patch("packages.services.grok_agent._grok_lock", AsyncMock()):
        result = await generate_single_clip(
            image_path=img_path,
            character_pose="A man sitting",
            camera_angle="Medium",
            style_suffix="Cinematic",
            motion_description="He talks",
            dialogue="Hello there",
            dialogue_mode=True, 
            duration="10s",
            aspect="16:9",
            external_page=page
        )
    
    assert result is not None
    assert result.exists()
    assert getattr(page, "_second_pass_started", False) is True

@pytest.mark.asyncio
@patch("packages.services.grok_agent.VideoSettings.verify_clip_duration", return_value=True)
@patch("packages.services.grok_agent.check_rate_limit", return_value=False)
@patch("packages.services.grok_agent.VideoSettings.configure", new_callable=AsyncMock)
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_generate_single_clip_extend_mode(
    mock_sleep,
    mock_configure, 
    mock_check_rate_limit, 
    mock_verify,
    tmp_path,
    monkeypatch
):
    """Test the extend video logic."""
    class FastForwardTime:
        def __init__(self):
            self.t = 0
        def time(self):
            return self.t

    mock_timer = FastForwardTime()
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(loop, 'time', mock_timer.time)
    
    async def fast_sleep(seconds):
        mock_timer.t += seconds
    mock_sleep.side_effect = fast_sleep

    page = MagicMock()
    page.url = "https://grok.com/imagine"
    page.is_closed = MagicMock(return_value=False)
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock()
    
    locators = {}
    def locator_side_effect(selector):
        if selector in locators: return locators[selector]
        m = MagicMock()
        m.count = AsyncMock(return_value=1)
        m.click = AsyncMock()
        m.fill = AsyncMock()
        
        if any(x in selector.lower() for x in ["generating", "thinking", "progressbar", "pulse", "spin", "cancel"]):
            m.is_visible = AsyncMock(side_effect=[True, True, False, False, False])
        else:
            m.is_visible = AsyncMock(return_value=True)
        
        m.first = m
        locators[selector] = m
        return m
    page.locator.side_effect = locator_side_effect
    
    async def mock_evaluate(js_code):
        if "Make video" in js_code:
            return True
        elif "querySelector('video')" in js_code:
            return {"ready": True, "duration": 10, "src": "blob:http://..."}
        return False
    page.evaluate.side_effect = mock_evaluate
    
    mock_download = AsyncMock()
    async def mock_save_as(path):
        with open(path, "wb") as f: f.write(b"video data" * 20000)
    mock_download.save_as.side_effect = mock_save_as
    
    dl_info = MagicMock()
    dl_info.value = AsyncMock(return_value=mock_download)
    class MockDownloadContext:
        async def __aenter__(self): return dl_info
        async def __aexit__(self, *args): pass
    page.expect_download.return_value = MockDownloadContext()

    fc_info = MagicMock()
    fc_info.value = AsyncMock()
    class MockFCContext:
        async def __aenter__(self): return fc_info
        async def __aexit__(self, *args): pass
    page.expect_file_chooser.return_value = MockFCContext()
    
    img_path = tmp_path / "test.png"
    img_path.touch()
    
    with patch("packages.services.grok_agent._grok_lock", AsyncMock()):
        result = await generate_single_clip(
            image_path=img_path,
            character_pose="A man sitting",
            camera_angle="Medium",
            style_suffix="Cinematic",
            motion_description="He talks",
            dialogue_mode=False, 
            needs_extend=True, 
            extend_duration="6s",
            duration="10s",
            aspect="16:9",
            external_page=page
        )
    
    assert result.exists()
    assert getattr(page, "_extend_started", False) is True
    assert mock_verify.call_count == 1
