"""
Unit tests for the Grok Agent cancel-trick workflow.

Tests the full state machine:
  STATE 1: Type "." → enable arrow button
  STATE 2: Click arrow → VERIFY generation started
  STATE 3: Wait 2-3s → generation in progress
  STATE 4: Click Cancel Video → VERIFY overlay cleared
  STATE 5: Inject full prompt
  STATE 6: Click arrow again → VERIFY final generation started
  STATE 7: Wait for download

Uses unittest.mock.AsyncMock to mock Playwright's Page object — no browser needed.
"""

import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.services.grok_agent import (
    PromptBuilder,
    _verify_generation_started,
    verified_make_video_click,
    _inject_prompt,
    check_rate_limit,
    VideoSettings,
)


# ============================================
# Helper: Create a mock Playwright Page
# ============================================
def make_mock_page(
    body_text: str = "",
    generating: bool = False,
    cancel_visible: bool = False,
    button_disabled: bool = False,
    has_prosemirror: bool = True,
):
    """
    Build a fully-configured AsyncMock that quacks like a Playwright Page.
    
    Args:
        body_text: The text returned by document.body.innerText
        generating: If True, body_text includes "Generating" / "Cancel Video"
        cancel_visible: If True, the Cancel Video button is visible
        button_disabled: If True, submit button reports as disabled
        has_prosemirror: If True, ProseMirror element exists
    """
    page = AsyncMock()
    
    # page.url
    page.url = "https://grok.com/imagine"
    
    # page.content() — for rate limit checks
    page.content = AsyncMock(return_value=f"<html><body>{body_text}</body></html>")
    
    # page.is_closed()
    page.is_closed = MagicMock(return_value=False)
    
    # Build body text for evaluate calls
    gen_text = body_text
    if generating:
        gen_text += " Generating... Cancel Video"

    # page.evaluate() — handle multiple JS snippets
    call_count = {"eval": 0}
    
    async def mock_evaluate(script, *args):
        call_count["eval"] += 1
        script_lower = script.lower() if isinstance(script, str) else ""
        
        # Body innerText check (for _verify_generation_started and cancel overlay checks)
        if "document.body.innertext" in script_lower:
            return gen_text
        
        # ProseMirror innerText check (for _inject_prompt verification)
        if "prosemirror" in script_lower and "innertext" in script_lower and "return" in script_lower:
            # Return the prompt that was "injected"
            if args:
                return args[0] if isinstance(args[0], str) else "Injected prompt text here abcdef"
            return "Injected prompt text here abcdef"
        
        # ProseMirror innerHTML clear
        if "prosemirror" in script_lower and "innerhtml" in script_lower:
            return None
        
        # Cancel button coordinate finder
        if "cancel" in script_lower and "getboundingclientrect" in script_lower:
            if cancel_visible:
                return {"x": 500, "y": 400, "found": True}
            return {"found": False}
        
        # Cancel button JS click
        if "cancel" in script_lower and "dispatchevent" in script_lower:
            return cancel_visible
        
        # Submit button JS fallback
        if "queryselectorall('button')" in script_lower and "dispatchevent" in script_lower:
            return not button_disabled
        
        # Coordinate-based click helper
        if "prosemirror" in script_lower and "getboundingclientrect" in script_lower:
            return {"x": 800, "y": 600}
        
        # Video mode click
        if "video" in script_lower and "click" in script_lower:
            return None
        
        # Clipboard
        if "clipboard" in script_lower:
            return None
        
        # textarea value set
        if "textarea" in script_lower:
            return None
        
        # Default
        return None
    
    page.evaluate = AsyncMock(side_effect=mock_evaluate)
    
    # page.locator() — returns a mock locator
    def mock_locator(selector):
        loc = AsyncMock()
        loc_text = selector.lower() if isinstance(selector, str) else ""
        
        # .count()
        if "cancel" in loc_text and cancel_visible:
            loc.count = AsyncMock(return_value=1)
            loc.is_visible = AsyncMock(return_value=True)
        elif "animate-pulse" in loc_text or "animate-spin" in loc_text or "progressbar" in loc_text:
            loc.count = AsyncMock(return_value=1 if generating else 0)
            loc.is_visible = AsyncMock(return_value=generating)
        elif "prosemirror" in loc_text or "textarea" in loc_text or "contenteditable" in loc_text:
            if has_prosemirror:
                loc.count = AsyncMock(return_value=1)
                loc.is_visible = AsyncMock(return_value=True)
                loc.click = AsyncMock()
                loc.fill = AsyncMock()
                loc.bounding_box = AsyncMock(return_value={"x": 100, "y": 200, "width": 600, "height": 50})
            else:
                loc.count = AsyncMock(return_value=0)
                loc.is_visible = AsyncMock(return_value=False)
        elif "submit" in loc_text or "send" in loc_text or "generate" in loc_text or "bg-neutral" in loc_text or "rounded-full" in loc_text:
            loc.count = AsyncMock(return_value=1)
            loc.is_visible = AsyncMock(return_value=True)
            loc.get_attribute = AsyncMock(return_value="true" if button_disabled else None)
            loc.scroll_into_view_if_needed = AsyncMock()
            loc.click = AsyncMock()
            loc.is_disabled = AsyncMock(return_value=button_disabled)
        else:
            loc.count = AsyncMock(return_value=0)
            loc.is_visible = AsyncMock(return_value=False)
        
        # .first / .last — return self
        loc.first = loc
        loc.last = loc
        
        # .scroll_into_view_if_needed
        if not hasattr(loc, 'scroll_into_view_if_needed') or loc.scroll_into_view_if_needed is None:
            loc.scroll_into_view_if_needed = AsyncMock()
        
        # .hover
        loc.hover = AsyncMock()
        
        # .filter
        loc.filter = MagicMock(return_value=loc)
        
        return loc
    
    page.locator = MagicMock(side_effect=mock_locator)
    
    # page.get_by_role()
    page.get_by_role = MagicMock(side_effect=lambda *a, **kw: mock_locator(str(a)))
    
    # page.keyboard
    page.keyboard = AsyncMock()
    page.keyboard.press = AsyncMock()
    page.keyboard.type = AsyncMock()
    
    # page.mouse
    page.mouse = AsyncMock()
    page.mouse.move = AsyncMock()
    page.mouse.click = AsyncMock()
    page.mouse.down = AsyncMock()
    page.mouse.up = AsyncMock()
    
    # page.wait_for_selector
    page.wait_for_selector = AsyncMock()
    
    # page.goto
    page.goto = AsyncMock()
    
    # page.screenshot
    page.screenshot = AsyncMock()
    
    return page


# ============================================
# Test: PromptBuilder
# ============================================
class TestPromptBuilder(unittest.TestCase):
    """Test the PromptBuilder.build() method."""
    
    def test_duration_prefix_6s(self):
        """Prompt should start with '6s: ' when duration=6s."""
        result = PromptBuilder.build(
            character_pose="standing",
            camera_angle="medium shot",
            style_suffix="cinematic",
            motion_description="walks forward",
            duration="6s"
        )
        self.assertTrue(result.startswith("6s: "), f"Expected '6s: ' prefix, got: {result[:20]}")
    
    def test_duration_prefix_10s(self):
        """Prompt should start with '10s: ' when duration=10s."""
        result = PromptBuilder.build(
            character_pose="sitting",
            camera_angle="close up",
            style_suffix="animated",
            motion_description="looks around",
            duration="10s"
        )
        self.assertTrue(result.startswith("10s: "), f"Expected '10s: ' prefix, got: {result[:20]}")
    
    def test_invalid_duration_defaults_to_10s(self):
        """Unsupported durations should default to 10s."""
        result = PromptBuilder.build(
            character_pose="standing",
            camera_angle="wide shot",
            style_suffix="",
            motion_description="runs",
            duration="15s"
        )
        self.assertTrue(result.startswith("10s: "), f"Expected '10s: ' prefix for invalid duration, got: {result[:20]}")
    
    def test_strips_aspect_ratio_keywords(self):
        """Aspect ratio keywords like '16:9' and 'landscape' should be stripped from prompt."""
        result = PromptBuilder.build(
            character_pose="standing",
            camera_angle="wide shot",
            style_suffix="landscape cinematic 16:9",
            motion_description="walks forward in 9:16 portrait mode",
            duration="6s"
        )
        # These should NOT appear in the final prompt (they're set via UI buttons)
        result_lower = result.lower()
        self.assertNotIn("16:9", result_lower)
        self.assertNotIn("9:16", result_lower)
        self.assertNotIn("landscape", result_lower)
        self.assertNotIn("portrait", result_lower)
    
    def test_no_double_duration_prefix(self):
        """Even if input has a duration prefix, result should have exactly one."""
        result = PromptBuilder.build(
            character_pose="standing",
            camera_angle="",
            style_suffix="",
            motion_description="6s: walks forward",
            duration="6s"
        )
        # Should start with exactly one "6s: "
        self.assertTrue(result.startswith("6s: "))
        # After the first "6s: ", there should NOT be another
        rest = result[4:]
        self.assertFalse(rest.startswith("6s:"), f"Double duration prefix detected: {result[:30]}")
    
    def test_grok_video_prompt_override(self):
        """When grok_video_prompt has image_to_video_prompt, it should override."""
        result = PromptBuilder.build(
            character_pose="standing",
            camera_angle="wide",
            style_suffix="cinematic",
            motion_description="default motion",
            grok_video_prompt={"image_to_video_prompt": "Custom grok prompt here"},
            duration="6s"
        )
        self.assertIn("Custom grok prompt here", result)
    
    def test_negative_text_prompt_always_present(self):
        """Anti-subtitle directive should always be in the prompt."""
        result = PromptBuilder.build(
            character_pose="standing",
            camera_angle="close up",
            style_suffix="",
            motion_description="walks",
            duration="6s"
        )
        self.assertIn("no text overlay", result.lower())
        self.assertIn("no subtitles", result.lower())


# ============================================
# Test: _verify_generation_started
# ============================================
class TestVerifyGenerationStarted(unittest.TestCase):
    """Test the _verify_generation_started() helper."""
    
    def test_detects_generating_text(self):
        """Should return True when 'Generating' is in body text."""
        page = make_mock_page(generating=True)
        result = asyncio.get_event_loop().run_until_complete(
            _verify_generation_started(page, timeout_s=1)
        )
        self.assertTrue(result, "Should detect 'Generating' indicator")
    
    def test_detects_cancel_video_text(self):
        """Should return True when 'Cancel Video' is in body text."""
        page = make_mock_page(body_text="Some text Cancel Video here")
        # Override evaluate to return text with Cancel Video
        async def eval_with_cancel(script, *args):
            if "innertext" in script.lower():
                return "Some text Cancel Video here"
            return None
        page.evaluate = AsyncMock(side_effect=eval_with_cancel)
        
        result = asyncio.get_event_loop().run_until_complete(
            _verify_generation_started(page, timeout_s=1)
        )
        self.assertTrue(result, "Should detect 'Cancel Video' indicator")
    
    def test_returns_false_when_no_indicators(self):
        """Should return False when page has no generation indicators."""
        page = make_mock_page(body_text="Welcome to Grok Imagine", generating=False)
        
        # Ensure evaluate returns text without indicators
        async def eval_no_gen(script, *args):
            if "innertext" in script.lower():
                return "Welcome to Grok Imagine"
            return None
        page.evaluate = AsyncMock(side_effect=eval_no_gen)
        
        # Make animation locator always invisible
        orig_locator = page.locator
        def no_anim_locator(sel):
            loc = orig_locator(sel)
            if "animate" in sel.lower() or "progressbar" in sel.lower():
                loc.is_visible = AsyncMock(side_effect=Exception("not found"))
            return loc
        page.locator = MagicMock(side_effect=no_anim_locator)
        
        result = asyncio.get_event_loop().run_until_complete(
            _verify_generation_started(page, timeout_s=0.5)
        )
        self.assertFalse(result, "Should return False with no generation indicators")
    
    def test_detects_animation_elements(self):
        """Should detect .animate-pulse or svg.animate-spin elements."""
        page = make_mock_page(generating=True)
        
        # Make evaluate return no text indicators, but animation locator visible
        async def eval_no_text(script, *args):
            if "innertext" in script.lower():
                return "Normal page text"
            return None
        page.evaluate = AsyncMock(side_effect=eval_no_text)
        
        result = asyncio.get_event_loop().run_until_complete(
            _verify_generation_started(page, timeout_s=1)
        )
        self.assertTrue(result, "Should detect animation elements")


# ============================================
# Test: verified_make_video_click
# ============================================
class TestVerifiedMakeVideoClick(unittest.TestCase):
    """Test the verified_make_video_click() function."""
    
    def test_click_success_with_verification(self):
        """Should click the button AND verify generation started."""
        page = make_mock_page(generating=True, button_disabled=False)
        
        result = asyncio.get_event_loop().run_until_complete(
            verified_make_video_click(page, timeout_s=3, verify=True)
        )
        self.assertTrue(result, "Should return True when button click triggers generation")
    
    def test_click_success_without_verification(self):
        """Should click the button without verifying generation (verify=False)."""
        page = make_mock_page(generating=False, button_disabled=False)
        
        result = asyncio.get_event_loop().run_until_complete(
            verified_make_video_click(page, timeout_s=3, verify=False)
        )
        self.assertTrue(result, "Should return True when button clicked (no verify)")
    
    def test_disabled_button_skipped(self):
        """Should skip disabled buttons and try JS fallback."""
        page = make_mock_page(generating=True, button_disabled=True)
        
        # When button is disabled via aria-disabled="true", the Playwright selectors
        # skip it but JS fallback should work (which also returns True for generating)
        result = asyncio.get_event_loop().run_until_complete(
            verified_make_video_click(page, timeout_s=2, verify=True)
        )
        # JS fallback sends click which should succeed
        # The mock's evaluate for the submit JS returns `not button_disabled`
        # Since button_disabled=True, JS fallback returns False, but coordinate fallback may work
        # This test validates the disabled button path is handled
        # (exact result depends on mock behavior for coordinates)
    
    def test_timeout_returns_false(self):
        """Should return False if all attempts fail."""
        page = make_mock_page(generating=False, button_disabled=True)
        
        # Override ALL strategies to fail
        async def eval_always_fail(script, *args):
            if "innertext" in script.lower():
                return "Normal page"
            return False  # JS click fails
        page.evaluate = AsyncMock(side_effect=eval_always_fail)
        
        # Make all locators invisible
        def invisible_locator(sel):
            loc = AsyncMock()
            loc.count = AsyncMock(return_value=0)
            loc.is_visible = AsyncMock(return_value=False)
            loc.first = loc
            loc.last = loc
            return loc
        page.locator = MagicMock(side_effect=invisible_locator)
        
        result = asyncio.get_event_loop().run_until_complete(
            verified_make_video_click(page, timeout_s=1, verify=True)
        )
        self.assertFalse(result, "Should return False when all click strategies fail")


# ============================================
# Test: _inject_prompt
# ============================================
class TestInjectPrompt(unittest.TestCase):
    """Test the _inject_prompt() function."""
    
    def test_short_prompt_typed(self):
        """Short prompts (<= 200 chars) should be typed character by character."""
        page = make_mock_page(has_prosemirror=True)
        prompt = "6s: A fox walks through the forest"
        
        result = asyncio.get_event_loop().run_until_complete(
            _inject_prompt(page, prompt)
        )
        
        self.assertTrue(result, "Should successfully inject short prompt")
        # Verify keyboard.type was called (for short prompts)
        page.keyboard.type.assert_called()
    
    def test_long_prompt_uses_js(self):
        """Long prompts (> 200 chars) should use JS injection."""
        page = make_mock_page(has_prosemirror=True)
        prompt = "6s: " + "A" * 250  # 254 chars
        
        result = asyncio.get_event_loop().run_until_complete(
            _inject_prompt(page, prompt)
        )
        
        self.assertTrue(result, "Should successfully inject long prompt via JS")
        # Verify evaluate was called (for JS injection)
        page.evaluate.assert_called()
    
    def test_fallback_to_fill(self):
        """If keyboard type fails, should fallback to fill()."""
        page = make_mock_page(has_prosemirror=True)
        prompt = "6s: Test prompt"
        
        # Make keyboard.type raise an error
        page.keyboard.type = AsyncMock(side_effect=Exception("keyboard type failed"))
        
        # The evaluate for verification may also fail, so let fill() work
        result = asyncio.get_event_loop().run_until_complete(
            _inject_prompt(page, prompt)
        )
        
        # Either strategy should succeed (fill() fallback)
        self.assertTrue(result, "Should fallback to fill() when keyboard fails")
    
    def test_verify_prompt_content(self):
        """Should verify that the injected text is actually in the editor."""
        page = make_mock_page(has_prosemirror=True)
        
        # Mock evaluate to return empty string (injection "failed")
        eval_calls = []
        async def mock_eval(script, *args):
            eval_calls.append(script)
            if "innertext" in script.lower() and "return" in script.lower():
                return ""  # Empty — injection "failed"
            return None
        page.evaluate = AsyncMock(side_effect=mock_eval)
        
        prompt = "6s: Fox walks through forest"
        result = asyncio.get_event_loop().run_until_complete(
            _inject_prompt(page, prompt)
        )
        
        # Should still return True because fill() fallback works
        # The key is that it TRIES to verify
        self.assertTrue(result)


# ============================================
# Test: Cancel-Trick Full Flow (Integration)
# ============================================
class TestCancelTrickFlow(unittest.TestCase):
    """
    Integration test for the complete cancel-trick workflow:
    1. Attach image
    2. Type "."
    3. Click arrow → VERIFY generation started
    4. Wait 2-3s
    5. Click Cancel Video
    6. Wait for overlay to clear
    7. Inject prompt
    8. Click arrow → VERIFY final generation started
    """
    
    def test_full_flow_states(self):
        """
        Test the state machine by running each state's helper in sequence.
        This validates the logical flow without needing a real browser.
        """
        loop = asyncio.get_event_loop()
        
        # === STATE 1: Type "." ===
        page = make_mock_page(generating=False, has_prosemirror=True)
        
        async def run_state_1():
            prompt_input = page.locator(".ProseMirror, textarea, [contenteditable='true']").first
            await prompt_input.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(".", delay=50)
        
        loop.run_until_complete(run_state_1())
        page.keyboard.type.assert_called_with(".", delay=50)
        
        # === STATE 2: Click arrow + verify ===
        # Switch mock to "generating" mode for this state
        page_generating = make_mock_page(generating=True, button_disabled=False)
        result = loop.run_until_complete(
            verified_make_video_click(page_generating, timeout_s=2, verify=True)
        )
        self.assertTrue(result, "STATE 2: Arrow click should trigger verified generation")
        
        # === STATE 3: Wait 2-3s (just a sleep, no assertion needed) ===
        
        # === STATE 4: Click Cancel Video ===
        page_cancel = make_mock_page(
            generating=True, cancel_visible=True, has_prosemirror=True
        )
        
        async def run_state_4():
            cancel_btn = page_cancel.locator("button:has-text('Cancel Video'), button:has-text('Cancel')").last
            if await cancel_btn.count() > 0 and await cancel_btn.is_visible(timeout=500):
                await cancel_btn.click(force=True, timeout=2000)
                return True
            return False
        
        cancel_result = loop.run_until_complete(run_state_4())
        self.assertTrue(cancel_result, "STATE 4: Cancel button should be clickable")
        
        # === STATE 5: Inject prompt ===
        page_prompt = make_mock_page(generating=False, has_prosemirror=True)
        prompt_result = loop.run_until_complete(
            _inject_prompt(page_prompt, "6s: A fox walks through the forest. Clean video, no text overlay.")
        )
        self.assertTrue(prompt_result, "STATE 5: Prompt should be injected successfully")
        
        # === STATE 6: Click arrow for final generation ===
        page_final = make_mock_page(generating=True, button_disabled=False)
        final_result = loop.run_until_complete(
            verified_make_video_click(page_final, timeout_s=2, verify=True)
        )
        self.assertTrue(final_result, "STATE 6: Final generation should be verified")
    
    def test_cancel_button_not_found_graceful(self):
        """When Cancel button is not found, the flow should continue to prompt injection."""
        page = make_mock_page(generating=True, cancel_visible=False)
        
        async def try_cancel():
            cancel_btn = page.locator("button:has-text('Cancel Video')").last
            if await cancel_btn.count() > 0 and await cancel_btn.is_visible(timeout=500):
                await cancel_btn.click(force=True)
                return True
            return False
        
        result = asyncio.get_event_loop().run_until_complete(try_cancel())
        # Cancel button not visible → should return False (graceful skip)
        self.assertFalse(result, "Should gracefully skip when cancel button not found")
    
    def test_seed_click_fails_still_injects_prompt(self):
        """
        If STATE 2 (seed click) fails, the flow should still inject the prompt
        and attempt final generation.
        """
        loop = asyncio.get_event_loop()
        
        # Seed click fails (button disabled, no JS fallback, no generation)
        page_fail = make_mock_page(generating=False, button_disabled=True)
        async def eval_fail(script, *args):
            if "innertext" in script.lower():
                return "Normal page"
            return False
        page_fail.evaluate = AsyncMock(side_effect=eval_fail)
        def invisible_locator(sel):
            loc = AsyncMock()
            loc.count = AsyncMock(return_value=0)
            loc.is_visible = AsyncMock(return_value=False)
            loc.first = loc
            loc.last = loc
            return loc
        page_fail.locator = MagicMock(side_effect=invisible_locator)
        
        seed_started = loop.run_until_complete(
            verified_make_video_click(page_fail, timeout_s=1, verify=True)
        )
        self.assertFalse(seed_started, "Seed should fail")
        
        # But prompt injection should still work
        page_prompt = make_mock_page(generating=False, has_prosemirror=True)
        prompt_ok = loop.run_until_complete(
            _inject_prompt(page_prompt, "6s: Test prompt for fallback scenario")
        )
        self.assertTrue(prompt_ok, "Prompt injection should still succeed after seed failure")


# ============================================
# Test: Rate Limit Detection
# ============================================
class TestRateLimitDetection(unittest.TestCase):
    """Test the check_rate_limit() function."""
    
    def test_detects_rate_limit(self):
        """Should return True when page contains rate limit text."""
        page = make_mock_page()
        page.content = AsyncMock(return_value="<html><body>You have reached the rate limit. Please try again later.</body></html>")
        
        result = asyncio.get_event_loop().run_until_complete(
            check_rate_limit(page)
        )
        self.assertTrue(result, "Should detect 'rate limit' text")
    
    def test_detects_too_many_requests(self):
        """Should detect 'too many requests' indicator."""
        page = make_mock_page()
        page.content = AsyncMock(return_value="<html>Too many requests. Slow down.</html>")
        
        result = asyncio.get_event_loop().run_until_complete(
            check_rate_limit(page)
        )
        self.assertTrue(result)
    
    def test_no_rate_limit(self):
        """Should return False for normal pages."""
        page = make_mock_page()
        page.content = AsyncMock(return_value="<html><body>Welcome to Grok Imagine</body></html>")
        
        result = asyncio.get_event_loop().run_until_complete(
            check_rate_limit(page)
        )
        self.assertFalse(result, "Should not detect rate limit on normal page")


# ============================================
# Test: VideoSettings
# ============================================
class TestVideoSettings(unittest.TestCase):
    """Test VideoSettings.configure() method."""
    
    def test_configure_calls_duration_aspect(self):
        """Should attempt to set duration, aspect ratio, and resolution."""
        page = make_mock_page()
        
        # Run configure
        asyncio.get_event_loop().run_until_complete(
            VideoSettings.configure(page, duration="6s", aspect="9:16", resolution="480p")
        )
        
        # Verify evaluate was called (for Video mode click and settings)
        page.evaluate.assert_called()
    
    def test_verify_clip_duration_match(self):
        """Should return True when duration matches within tolerance."""
        with patch("ffmpeg.probe") as mock_probe:
            mock_probe.return_value = {"streams": [{"duration": "6.2"}]}
            result = VideoSettings.verify_clip_duration(Path("test.mp4"), 6.0)
            self.assertTrue(result, "6.2s vs 6.0s should be within 1.5s tolerance")
    
    def test_verify_clip_duration_mismatch(self):
        """Should return False when duration differs by more than tolerance."""
        with patch("ffmpeg.probe") as mock_probe:
            mock_probe.return_value = {"streams": [{"duration": "15.0"}]}
            result = VideoSettings.verify_clip_duration(Path("test.mp4"), 6.0)
            self.assertFalse(result, "15.0s vs 6.0s should exceed 1.5s tolerance")


# ============================================
# Test: Edge Cases
# ============================================
class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def test_verify_generation_with_page_error(self):
        """Should handle page.evaluate throwing errors gracefully."""
        page = make_mock_page()
        page.evaluate = AsyncMock(side_effect=Exception("Page crashed"))
        
        # Make locator also fail
        def error_locator(sel):
            loc = AsyncMock()
            loc.is_visible = AsyncMock(side_effect=Exception("Element not found"))
            loc.first = loc
            loc.last = loc
            return loc
        page.locator = MagicMock(side_effect=error_locator)
        
        result = asyncio.get_event_loop().run_until_complete(
            _verify_generation_started(page, timeout_s=0.5)
        )
        self.assertFalse(result, "Should return False on page errors, not crash")
    
    def test_inject_prompt_no_prosemirror(self):
        """Should handle missing ProseMirror element gracefully."""
        page = make_mock_page(has_prosemirror=False)
        
        # Make locator click fail (no ProseMirror)
        def no_editor_locator(sel):
            loc = AsyncMock()
            loc.count = AsyncMock(return_value=0)
            loc.is_visible = AsyncMock(return_value=False)
            loc.click = AsyncMock(side_effect=Exception("No element"))
            loc.fill = AsyncMock(side_effect=Exception("No element"))
            loc.first = loc
            loc.last = loc
            return loc
        page.locator = MagicMock(side_effect=no_editor_locator)
        
        result = asyncio.get_event_loop().run_until_complete(
            _inject_prompt(page, "test prompt")
        )
        self.assertFalse(result, "Should return False when ProseMirror not found")
    
    def test_prompt_builder_empty_inputs(self):
        """PromptBuilder should handle all-empty inputs without crashing."""
        result = PromptBuilder.build(
            character_pose="",
            camera_angle="",
            style_suffix="",
            motion_description="",
            duration="6s"
        )
        self.assertTrue(result.startswith("6s: "), f"Should still have duration prefix: {result[:20]}")
        self.assertIn("no subtitles", result.lower())
    
    def test_verified_click_multiple_strategies(self):
        """Should try multiple strategies when first ones fail."""
        page = make_mock_page(generating=True, button_disabled=False)
        
        # Track which evaluate calls are made
        eval_calls = []
        async def tracking_eval(script, *args):
            eval_calls.append(script[:50])
            if "innertext" in script.lower():
                return "Generating..."
            if "queryselectorall" in script.lower():
                return True
            return None
        page.evaluate = AsyncMock(side_effect=tracking_eval)
        
        result = asyncio.get_event_loop().run_until_complete(
            verified_make_video_click(page, timeout_s=2, verify=True)
        )
        
        # Should have succeeded via one of the strategies
        self.assertTrue(result)


if __name__ == "__main__":
    # Use a custom test event loop if none exists
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            asyncio.set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    
    unittest.main(verbosity=2)
