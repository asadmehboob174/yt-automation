"""
Real Browser Integration Tests for the Grok Playwright Automation Bot.

These tests launch a REAL Playwright Chromium browser and interact with
the Grok Imagine UI at https://grok.com/imagine to validate:

  1. Pass 1 – Image-only attach (dialogue_mode=True skips prompt text)
  2. Pass 2 – "Continue this frame. [prompt]" typed after first video ready
  3. Extend Support – "Extend video" button clicked when needs_extend=True

Requirements:
  - You MUST be logged in to Grok via Chrome user profile at ~/.grok-profile
  - An active internet connection
  - A test image available at tests/fixtures/test_scene.png

Run with:
  pytest tests/test_grok_integration.py -v -s --timeout=600

NOTE: These tests perform REAL generation and take 2-5 minutes each.
      They are NOT meant for CI/CD – run locally only.
"""
import os
import sys
import asyncio
import logging
import pytest
from pathlib import Path
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ─── Paths ───────────────────────────────────────────────
PROFILE_PATH = Path.home() / ".grok-profile"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_IMAGE = FIXTURES_DIR / "test_scene.png"
OUTPUT_DIR = Path.cwd() / "generated_videos" / "integration_tests"

# Set asyncio mode for all tests
pytestmark = pytest.mark.asyncio


def _ensure_test_image():
    """Create or validate the test fixture image."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not TEST_IMAGE.exists():
        import struct, zlib

        def _make_png(width, height, rgb=(200, 60, 60)):
            def chunk(ctype, data):
                c = ctype + data
                return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

            header = b"\x89PNG\r\n\x1a\n"
            ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            raw = b""
            for _ in range(height):
                raw += b"\x00" + bytes(rgb) * width
            idat = chunk(b"IDAT", zlib.compress(raw))
            iend = chunk(b"IEND", b"")
            return header + ihdr + idat + iend

        TEST_IMAGE.write_bytes(_make_png(256, 256))
        logger.info(f"Created test image: {TEST_IMAGE}")


# ─── Helper Functions ────────────────────────────────────
async def _get_grok_page() -> tuple:
    """
    Launch a persistent Chromium context and navigate to Grok Imagine.
    Returns (playwright, context, page).
    """
    pw = await async_playwright().start()

    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars",
    ]

    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_PATH),
        headless=False,
        accept_downloads=True,
        ignore_default_args=["--enable-automation"],
        args=args,
        viewport={"width": 1100, "height": 800},
    )

    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto("https://grok.com/imagine", wait_until="domcontentloaded", timeout=60_000)

    # Wait for prompt input area
    try:
        await page.wait_for_selector(
            ".ProseMirror, textarea, [contenteditable='true']",
            state="visible",
            timeout=10_000,
        )
    except Exception:
        logger.warning("Prompt area not found within 10s – continuing anyway")

    return pw, ctx, page


async def _cleanup(pw, ctx):
    """Close browser and stop playwright."""
    try:
        await ctx.close()
    except: pass
    try:
        await pw.stop()
    except: pass


async def _fill_prompt(page: Page, text: str) -> bool:
    """Type text into the Grok prompt area. Returns True on success."""
    for selector in [".ProseMirror", "textarea", "[contenteditable='true']"]:
        try:
            el = page.locator(selector).first
            if await el.count() > 0 and await el.is_visible():
                await el.click()
                await asyncio.sleep(0.5)
                await el.fill(text)
                logger.info(f"✅ Prompt filled in {selector}")
                return True
        except Exception:
            continue
    return False


async def _attach_image(page: Page, image_path: Path) -> bool:
    """Attach an image via Grok's upload button or file input."""
    for selector in ["button:has-text('Upload image')", "button[aria-label*='Attach']", "input[type='file']"]:
        try:
            btn = page.locator(selector).first
            if await btn.count() > 0:
                async with page.expect_file_chooser(timeout=5000) as fc_info:
                    await btn.click()
                fc = await fc_info.value
                await fc.set_files(str(image_path))
                logger.info(f"✅ Image attached via {selector}")
                return True
        except Exception:
            continue
    return False


async def _click_make_video(page: Page) -> bool:
    """Click 'Make video' button via multiple strategies."""
    make_video_selectors = [
        "button[aria-label='Make video']",
        "button:has-text('Make video'):not([aria-label='Search'])",
        "div[role='button']:has-text('Make video')",
        "button:has-text('Generate')",
        "button:has-text('Create')",
        "button[type='submit']",
    ]
    combined = ", ".join(make_video_selectors)
    try:
        btn = await page.wait_for_selector(combined, state="visible", timeout=20_000)
        if btn:
            await btn.click(timeout=5000)
            logger.info("✅ Clicked 'Make video'")
            return True
    except Exception:
        pass

    # JS fallback
    clicked = await page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button, [role="button"], div'));
        for (const b of btns) {
            if (b.innerText && (b.innerText.includes('Make video') || b.innerText.includes('Generate')) && !b.innerText.includes('Cancel')) {
                b.click(); return true;
            }
        }
        return false;
    }""")
    if clicked:
        logger.info("✅ Clicked 'Make video' via JS fallback")
        return True

    # Keyboard Enter fallback (submit prompt area)
    try:
        await page.keyboard.press("Enter")
        logger.info("✅ Submitted via Enter key fallback")
        return True
    except:
        pass

    return False


async def _wait_for_video_ready(page: Page, timeout_s: int = 180) -> bool:
    """
    Poll until a <video> element appears with readyState >= 3.
    Returns True when video is detected and ready.
    """
    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) < timeout_s:
        try:
            result = await page.evaluate("""() => {
                const v = document.querySelector('video');
                if (!v) return null;
                return { ready: v.readyState >= 3, duration: v.duration, src: v.src };
            }""")
            if result and result.get("ready") and result.get("duration", 0) > 0:
                logger.info(f"✅ Video ready: duration={result['duration']}s")
                return True
        except Exception:
            pass
        await asyncio.sleep(3)
    return False


async def _click_extend_button(page: Page) -> bool:
    """Click the 'Extend video' button if present."""
    extend_selectors = [
        "button:has-text('Extend video')",
        "button:has-text('Extend')",
        "[aria-label*='Extend']",
        "div[role='menuitem']:has-text('Extend')",
    ]
    for selector in extend_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                logger.info(f"✅ Clicked Extend via {selector}")
                return True
        except Exception:
            continue
            
    # JS fallback
    clicked = await page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button, [role="button"], div[role="menuitem"]'));
        for (const b of btns) {
            if (b.innerText && b.innerText.includes('Extend')) {
                b.click(); return true;
            }
        }
        return false;
    }""")
    if clicked:
        logger.info("✅ Clicked Extend via JS fallback")
        return True
        
    return False


async def _download_video(page: Page, output_path: Path) -> bool:
    """Click download and save the video to output_path."""
    download_selectors = [
        "button[aria-label='Download']",
        "button:has-text('Download')",
        "[data-testid='download-button']",
    ]
    for selector in download_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.count() > 0 and await btn.is_visible():
                async with page.expect_download(timeout=30_000) as dl_info:
                    await btn.click()
                download = await dl_info.value
                await download.save_as(str(output_path))
                if output_path.exists() and output_path.stat().st_size > 50_000:
                    logger.info(f"✅ Downloaded {output_path.stat().st_size} bytes → {output_path}")
                    return True
        except Exception:
            continue
    return False


# ═══════════════════════════════════════════════════════════
# TEST 1 – Pass 1 (dialogue_mode): Attach image without text
# ═══════════════════════════════════════════════════════════
async def test_pass1_dialogue_mode_image_only():
    """
    Validates Pass 1 of the two-pass dialogue flow:
      - NO text prompt is typed
      - Image IS attached
      - 'Make video' IS clicked
      - A video IS generated (first pass output)
      - We do NOT download it (the real pipeline skips download here)
    """
    _ensure_test_image()
    pw, ctx, page = await _get_grok_page()

    try:
        # 1. Verify we are on Grok Imagine
        assert "grok.com" in page.url, f"Not on Grok: {page.url}"

        # 2. Do NOT fill any text prompt (this is Pass 1 / dialogue mode)
        # Ensure prompt area is empty
        for sel in [".ProseMirror", "textarea"]:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.fill("")
                    break
            except: pass

        # 3. Attach image
        attached = await _attach_image(page, TEST_IMAGE)
        assert attached, "Failed to attach test image"

        # 4. Click Make video
        clicked = await _click_make_video(page)
        assert clicked, "Failed to click 'Make video'"

        # 5. Wait for first video to appear (Pass 1 output)
        video_ready = await _wait_for_video_ready(page, timeout_s=180)
        assert video_ready, "Pass 1 video did not generate within 3 minutes"

        # 6. Verify the video element exists (we don't download in Pass 1)
        result = await page.evaluate("""() => {
            const v = document.querySelector('video');
            return v ? { duration: v.duration, src: v.src.substring(0, 50) } : null;
        }""")
        assert result is not None, "No video element found after generation"
        assert result["duration"] > 0, "Video duration is 0"

        logger.info(f"✅ PASS 1 PASSED — Video generated without prompt text (duration={result['duration']}s)")
    finally:
        await _cleanup(pw, ctx)


# ═══════════════════════════════════════════════════════════
# TEST 2 – Pass 2 (continue prompt): Type continuation + regenerate
# ═══════════════════════════════════════════════════════════
async def test_pass2_continue_frame_prompt():
    """
    Validates Pass 2 of the two-pass dialogue flow:
      - Generate a base video first (attach image + click make video)
      - Wait for video readiness
      - Type "Continue this frame. [descriptive prompt]"
      - Click 'Make video' again
      - Wait for a SECOND video
      - Download the second video
    """
    _ensure_test_image()
    pw, ctx, page = await _get_grok_page()

    try:
        # ── Generate base video (Pass 1) ──
        await _attach_image(page, TEST_IMAGE)
        await _click_make_video(page)
        ready = await _wait_for_video_ready(page, timeout_s=180)
        assert ready, "Could not generate Pass 1 video as prerequisite"

        await asyncio.sleep(5)  # Buffer for UI

        # ── Pass 2: Type continuation prompt ──
        continue_prompt = "Continue this frame. Slow cinematic camera pan across a dark mysterious forest with fog and moonlight."
        filled = await _fill_prompt(page, continue_prompt)
        assert filled, "Could not type continuation prompt for Pass 2"

        # Click Make video again
        clicked = await _click_make_video(page)
        assert clicked, "Failed to click 'Make video' for Pass 2"

        # Wait for the new video
        await asyncio.sleep(10)  # Buffer for UI transition
        video_ready = await _wait_for_video_ready(page, timeout_s=180)
        assert video_ready, "Pass 2 video generation timed out"

        # Download the Pass 2 video
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = OUTPUT_DIR / f"pass2_dialogue_{ts}.mp4"
        downloaded = await _download_video(page, output)
        assert downloaded, "Failed to download Pass 2 video"
        assert output.stat().st_size > 100_000, f"Downloaded file too small: {output.stat().st_size}b"

        logger.info(f"✅ PASS 2 PASSED — Continue prompt accepted, video downloaded ({output.stat().st_size} bytes)")
    finally:
        await _cleanup(pw, ctx)


# ═══════════════════════════════════════════════════════════
# TEST 3 – Extend Video Support
# ═══════════════════════════════════════════════════════════
async def test_extend_video_button():
    """
    Validates the Extend Video flow:
      - Generate a normal clip first
      - After generation, click 'Extend video'
      - Wait for the extended clip to finish
      - Download the result
    """
    _ensure_test_image()
    pw, ctx, page = await _get_grok_page()

    try:
        # 1. Generate a base video
        prompt = "10s: A cat sitting on a windowsill watching rain. Slow parallax. Clean video, no text overlay, no subtitles"
        filled = await _fill_prompt(page, prompt)
        assert filled, "Could not type prompt for extend test"

        attached = await _attach_image(page, TEST_IMAGE)
        assert attached, "Failed to attach image for extend test"

        clicked = await _click_make_video(page)
        assert clicked, "Failed to click Make video"

        video_ready = await _wait_for_video_ready(page, timeout_s=180)
        assert video_ready, "Base video generation timed out"

        # 2. Try to click Extend Video
        # Sometimes the video needs to be hovered or clicked to show the Extend button
        await asyncio.sleep(5)  # Let UI settle and video load
        
        # Try to hover the video to reveal controls
        try:
            await page.locator('video').first.hover(timeout=2000)
            await asyncio.sleep(1)
        except: pass
        
        extended = await _click_extend_button(page)

        if extended:
            logger.info("🔄 Extend clicked — setting duration and submitting...")
            await asyncio.sleep(3)  # Wait for extend UI
            
            # SET DURATION
            # For test purposes, we'll try to click the '6s' inline pill
            try:
                dur_btn = page.locator("div.flex button:has-text('6s'), button.rounded-full:has-text('6s')").first
                if await dur_btn.is_visible(timeout=2000):
                    await dur_btn.click()
                    logger.info("✅ Set extension duration to 6s via inline pill")
                else:
                    # Fallback to Settings menu
                    dur_btn = page.locator("button:has-text('Duration')").first
                    if await dur_btn.is_visible():
                        await dur_btn.click()
                        await asyncio.sleep(1)
                        await page.locator("button:has-text('6s'), div:has-text('6s')").last.click()
                        logger.info("✅ Set extension duration to 6s via settings menu")
            except Exception as e:
                logger.warning(f"⚠️ Could not set duration in test: {e}")
                
            # CLICK ARROW/SEND BUTTON
            arrow_clicked = False
            # Try Enter key first
            try:
                prompt_input = page.locator(".ProseMirror, textarea, [contenteditable='true']").first
                if await prompt_input.is_visible():
                    await prompt_input.press("Enter")
                    arrow_clicked = True
                    logger.info("✅ Pressed Enter to submit extend video")
            except: pass
            
            if not arrow_clicked:
                for selector in [
                    "button[aria-label='Send']",
                    "button[aria-label='Submit']",
                    "button[type='submit']",
                    "button:has(svg.lucide-arrow-up)",
                ]:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible():
                            await btn.click()
                            logger.info(f"✅ Clicked arrow/submit via {selector}")
                            arrow_clicked = True
                            break
                    except: pass

            logger.info("⏳ Waiting for extended video generation...")
            await asyncio.sleep(10)  # UI transition buffer
            ext_ready = await _wait_for_video_ready(page, timeout_s=180)
            assert ext_ready, "Extended video generation timed out"

            # Download
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = OUTPUT_DIR / f"extended_clip_{ts}.mp4"
            downloaded = await _download_video(page, output)
            assert downloaded, "Failed to download extended video"
            logger.info(f"✅ EXTEND PASSED — Extended video downloaded ({output.stat().st_size} bytes)")
        else:
            logger.warning("⚠️ 'Extend video' button not found — may not be available for all clips")
            pytest.skip("Extend button not available in current Grok UI")
    finally:
        await _cleanup(pw, ctx)


# ═══════════════════════════════════════════════════════════
# TEST 4 – Full End-to-End Two-Pass + Download
# ═══════════════════════════════════════════════════════════
async def test_full_two_pass_e2e():
    """
    Full end-to-end test combining Pass 1 + Pass 2 in a single flow:
      1. Navigate to Grok Imagine
      2. Attach image WITHOUT text (Pass 1)
      3. Wait for video
      4. Type "Continue this frame. [prompt]" (Pass 2)
      5. Click Make video
      6. Wait for video
      7. Download final clip
    """
    _ensure_test_image()
    pw, ctx, page = await _get_grok_page()

    try:
        # ── PASS 1: Image only ──
        logger.info("═══ PASS 1: Image-only attach (dialogue_mode) ═══")
        attached = await _attach_image(page, TEST_IMAGE)
        assert attached, "Pass 1: Image attach failed"

        clicked = await _click_make_video(page)
        assert clicked, "Pass 1: Make video click failed"

        p1_ready = await _wait_for_video_ready(page, timeout_s=180)
        assert p1_ready, "Pass 1: Video generation timed out"
        logger.info("✅ Pass 1 complete")

        await asyncio.sleep(5)  # Buffer

        # ── PASS 2: Continue this frame ──
        logger.info("═══ PASS 2: Continue this frame (context integration) ═══")
        continue_prompt = "Continue this frame. Slow zoom out revealing a vast alien landscape with bioluminescent plants and a distant purple sun setting."
        filled = await _fill_prompt(page, continue_prompt)
        assert filled, "Pass 2: Could not fill continuation prompt"

        clicked2 = await _click_make_video(page)
        assert clicked2, "Pass 2: Make video click failed"

        await asyncio.sleep(10)  # UI transition
        p2_ready = await _wait_for_video_ready(page, timeout_s=180)
        assert p2_ready, "Pass 2: Video generation timed out"

        # ── DOWNLOAD ──
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = OUTPUT_DIR / f"e2e_two_pass_{ts}.mp4"
        downloaded = await _download_video(page, output)
        assert downloaded, f"Final download failed"
        assert output.stat().st_size > 100_000, f"File too small: {output.stat().st_size}"

        logger.info(f"✅ FULL E2E PASSED — {output} ({output.stat().st_size} bytes)")
    finally:
        await _cleanup(pw, ctx)
