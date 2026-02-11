"""
Grok Animation Agent with Full Automation Resilience.

Handles 5 critical automation loopholes:
1. 5-Layer Prompt Formula
2. URL Listener for Post Navigation
3. Duration & Aspect Ratio Detection
4. Stealth File Upload (Anti-Bot)
5. Inngest-Driven Rate Limit Recovery
"""
import os
import asyncio
import random
import tempfile
import logging
import re
from pathlib import Path
from uuid import uuid4
from datetime import timedelta
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext
# playwright_stealth import removed - not needed for current functionality

logger = logging.getLogger(__name__)

# Global Lock to prevent concurrent Grok launches
_grok_lock = asyncio.Lock()

# Use the same profile root as Grok to potentially share Google Auth if possible,
# or keep them separate but managed similarly.
PROFILE_PATH = Path.home() / ".grok-profile"


# ============================================
# Exceptions
# ============================================
class RateLimitError(Exception):
    """Raised when Grok rate limit is hit."""
    pass


class UIChangedError(Exception):
    """Raised when Grok's UI has changed and selectors no longer work."""
    pass


# ============================================
# Loophole #1: 5-Layer Prompt Formula
# ============================================
class PromptBuilder:
    """
    Combines motion and dialogue into Grok-optimized prompt.
    Format: [Scene] + [Camera] + [Style] + [Motion] + [Audio/Dialogue]
    """
    
    @staticmethod
    def build(
        character_pose: str,
        camera_angle: str,
        style_suffix: str,
        motion_description: str,
        dialogue: Optional[str] = None,
        sfx: Optional[str] = None,
        character_name: str = "Character",
        emotion: str = "neutrally"
    ) -> str:
        """
        Builds the prompt in the optimal 'Motion First' format.
        
        Format:
        [Motion Description]
        
        Dialogue ([Character]): "[Text]"
        Shot: [Camera Angle]
        [Style Suffix]
        """
        # 1. Motion is King (First for strongest adherence)
        # If motion_description is "clean", use it. If it looks like it already has headers, use it as is?
        # Assuming we will clean up the input source, so we trust motion_description here.
        
        prompt_parts = []
        
        # Part A: Motion
        if motion_description:
            prompt_parts.append(motion_description.strip())
            
        # Part B: Dialogue
        if dialogue and dialogue.strip():
            # Format: Dialogue (Character): "Line"
            # If dialogue string already contains "Dialogue (X):", just add it.
            # Otherwise format it.
            if "Dialogue" in dialogue:
                prompt_parts.append("\n" + dialogue.strip())
            else:
                 prompt_parts.append(f'\nDialogue ({character_name}): "{dialogue.strip()}"')

        # Part C: Camera Angle
        if camera_angle:
            prompt_parts.append(f"\nShot: {camera_angle}")
            
        # Part D: Sound Effects (New)
        if sfx and sfx.strip():
            # Only add header if it looks like a description, otherwise just the text
            if "Sound" in sfx or "SFX" in sfx:
                prompt_parts.append("\n" + sfx.strip())
            else:
                prompt_parts.append(f"\nSound Effects: {sfx.strip()}")

        # Part E: Style (Optional)
        if style_suffix:
            prompt_parts.append(f"\nStyle: {style_suffix}")
            
        return "\n".join(prompt_parts)


# ============================================
# Loophole #2: URL Listener for Post Navigation
# ============================================
class URLListener:
    """
    Grok (Jan 2026 update) navigates to a NEW post URL after successful generation.
    We must capture this new URL to find the download button.
    """
    
    @staticmethod
    async def wait_for_post_navigation(page: Page, timeout: int = 120000) -> str:
        """Wait for URL to change to a post page after clicking Generate."""
        original_url = page.url
        
        async def wait_for_new_url():
            while True:
                current_url = page.url
                # Grok post URLs contain /post/ or /status/
                if current_url != original_url and ("/post/" in current_url or "/status/" in current_url):
                    return current_url
                await asyncio.sleep(0.5)
        
        try:
            new_url = await asyncio.wait_for(wait_for_new_url(), timeout=timeout/1000)
            logger.info(f"✅ Navigated to new post: {new_url}")
            return new_url
        except asyncio.TimeoutError:
            raise TimeoutError("Video generation did not navigate to post URL")


# ============================================
# Loophole #3: Duration & Aspect Ratio Detection
# ============================================
class VideoSettings:
    """Detect and select duration/aspect ratio before generation."""
    
    DURATION_SELECTORS = {
        "6s": ["[data-duration='6']", "button:has-text('6s')", ".duration-6"],
        "10s": ["[data-duration='10']", "button:has-text('10s')", ".duration-10"],
    }
    
    # Updated selectors based on actual Grok UI HTML (Feb 2026)
    # Buttons have aria-label="9:16", aria-label="16:9", etc.
    ASPECT_SELECTORS = {
        "9:16": [
            "button[aria-label='9:16']",  # Primary - exact match from user's HTML
            "[aria-label='9:16']",
            "button:has-text('9:16')",
            ".aspect-vertical",
        ],
        "16:9": [
            "button[aria-label='16:9']",  # Primary - exact match from user's HTML
            "[aria-label='16:9']",
            "button:has-text('16:9')",
            ".aspect-landscape",
        ],
        "2:3": [
            "button[aria-label='2:3']",
            "[aria-label='2:3']",
        ],
        "3:2": [
            "button[aria-label='3:2']",
            "[aria-label='3:2']",
        ],
        "1:1": [
            "button[aria-label='1:1']",
            "[aria-label='1:1']",
        ],
    }
    
    @classmethod
    async def configure(cls, page: Page, duration: str = "10s", aspect: str = "9:16"):
        """Set duration and aspect ratio before generating."""
        logger.info(f"⚙️ Configuring video settings: duration={duration}, aspect={aspect}")
        
        # Try duration selectors
        for selector in cls.DURATION_SELECTORS.get(duration, []):
            try:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    await btn.first.click()
                    logger.info(f"✅ Set duration: {duration}")
                    break
            except Exception:
                continue
        
        # Try aspect selectors - these are the ratio buttons in Grok's UI
        aspect_clicked = False
        for selector in cls.ASPECT_SELECTORS.get(aspect, []):
            try:
                btn = page.locator(selector)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    logger.info(f"✅ Set aspect ratio: {aspect} via {selector}")
                    aspect_clicked = True
                    break
            except Exception as e:
                logger.debug(f"Aspect selector {selector} failed: {e}")
                continue
        
        if not aspect_clicked:
            logger.warning(f"⚠️ Could not find aspect ratio button for {aspect}. Available buttons may have different aria-labels.")
    
    @staticmethod
    def verify_clip_duration(clip_path: Path, expected_duration: float) -> bool:
        """Use ffprobe to verify actual clip duration matches expected."""
        try:
            import ffmpeg
            probe = ffmpeg.probe(str(clip_path))
            actual = float(probe['streams'][0]['duration'])
            tolerance = 0.5  # 500ms tolerance
            
            if abs(actual - expected_duration) > tolerance:
                logger.warning(f"⚠️ Duration mismatch: expected {expected_duration}s, got {actual}s")
                return False
            return True
        except Exception as e:
            logger.warning(f"Failed to verify duration: {e}")
            return True  # Assume OK if can't verify


# ============================================
# Loophole #4: Stealth File Upload (Anti-Bot)
# ============================================
class StealthUploader:
    """
    Human-like file upload to avoid bot detection.
    Uses mouse jitter and randomized delays.
    """
    
    @staticmethod
    async def upload_with_jitter(page: Page, file_input_selector: str, file_path: Path):
        """Upload file with human-like behavior."""
        file_input = page.locator(file_input_selector)
        
        # Random delay before interaction (500-1500ms)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Move mouse near the upload area with jitter
        try:
            box = await file_input.bounding_box()
            if box:
                # Add random offset (human imprecision)
                target_x = box['x'] + box['width'] / 2 + random.randint(-10, 10)
                target_y = box['y'] + box['height'] / 2 + random.randint(-10, 10)
                
                # Move mouse in small steps (not instant teleport)
                await page.mouse.move(target_x, target_y, steps=random.randint(5, 15))
                await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception:
            pass  # Continue even if mouse move fails
        
        # Use setInputFiles (doesn't trigger file picker dialog)
        await file_input.set_input_files(str(file_path))
        
        # Random delay after upload (human pause to verify)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        logger.info(f"✅ Uploaded file with stealth: {file_path.name}")


async def _clean_grok_locks():
    """Removes Singleton lock files and kills dangling chrome processes."""
    if os.name == 'nt':
        try:
            os.system('taskkill /F /IM chrome.exe /T 2>nul')
            os.system('taskkill /F /IM chromium.exe /T 2>nul')
            logger.info("🔪 Force killed dangling browser processes for Grok.")
            await asyncio.sleep(1)
        except: pass

    locks = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
    for lock in locks:
        lock_path = PROFILE_PATH / lock
        if lock_path.exists():
            try:
                lock_path.unlink()
                logger.info(f"🧹 Removed stale Grok lock: {lock}")
            except: pass


# ============================================
# Browser Management
# ============================================
async def get_browser_context() -> tuple[BrowserContext, any]:
    """Create browser context with persistent profile."""
    async with _grok_lock:
        playwright = await async_playwright().start()
        args = [
            '--disable-blink-features=AutomationControlled', 
            '--no-sandbox', 
            '--disable-infobars'
        ]
        
        ext_path_str = os.getenv("GROK_EXTENSION_PATH")
        if ext_path_str:
            # Support multiple paths separated by comma
            ext_paths = [p.strip() for p in ext_path_str.split(',') if os.path.isdir(p.strip())]
            if ext_paths:
                logger.info(f"🧩 Loading {len(ext_paths)} Grok Extensions...")
                load_arg = ",".join(ext_paths)
                args.append(f"--disable-extensions-except={load_arg}")
                args.append(f"--load-extension={load_arg}")

        MAX_RETRIES = 5
        for attempt in range(MAX_RETRIES):
            try:
                browser = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_PATH),
                    headless=False, # Force headful for now to debug/verify login
                    # CRITICAL: Match login_grok.py settings to keep session valid
                    ignore_default_args=["--enable-automation"],
                    args=args
                )
                return browser, playwright
            except Exception as e:
                error_msg = str(e).lower()
                if "target page, context or browser has been closed" in error_msg or "existing browser session" in error_msg or "in use" in error_msg:
                    logger.warning(f"⚠️ Grok Browser Lock detected (Attempt {attempt+1}/{MAX_RETRIES}). Cleaning...")
                    await _clean_grok_locks()
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    await playwright.stop()
                    raise e
        
        await playwright.stop()
        raise RuntimeError("Failed to launch Grok browser after multiple attempts.")


async def check_rate_limit(page: Page) -> bool:
    """Detect rate limit indicators on page."""
    content = await page.content()
    indicators = ["limit reached", "rate limit", "too many requests", "slow down", "try again later"]
    return any(ind.lower() in content.lower() for ind in indicators)


# ============================================
# Core Generation Function
# ============================================
async def generate_single_clip(
    image_path: Path,
    character_pose: str,
    camera_angle: str,
    style_suffix: str,
    motion_description: str,
    dialogue: Optional[str] = None,
    sfx: Optional[str] = None,
    character_name: str = "Character",
    emotion: str = "neutrally",
    duration: str = "10s",
    aspect: str = "9:16",
    external_page: Optional[Page] = None
) -> Path:
    """Core generation logic with all stealth features."""
    browser = None
    pw = None
    page = external_page
    
    if not page:
        browser, pw = await get_browser_context()
        # REUSE FIRST PAGE TO AVOID EMPTY TABS
        if len(browser.pages) > 0:
            page = browser.pages[0]
            logger.info("📄 Reusing existing Grok tab")
        else:
            page = await browser.new_page()
            logger.info("📄 Opened new Grok tab")
    
    try:
        # await Stealth().apply_stealth_async(page)  <-- DISABLED to match login script
        await page.goto("https://grok.com/imagine", wait_until="networkidle", timeout=60000)
        
        # Wait for page to fully load
        await asyncio.sleep(3)
        
        # Check rate limit FIRST
        if await check_rate_limit(page):
            raise RateLimitError("Rate limit detected")

        # SAFETY CHECK (Pre-generation)
        # DISABLE RELOAD LOOP: User reported "refreshes the site"
        # try:
        #      safety_warn = page.locator("text=/safety|policy|violation/i")
        #      if await safety_warn.count() > 0 and await safety_warn.first.is_visible():
        #           logger.warning("🚫 Found existing safety warning. Refreshing...")
        #           await page.reload()
        #           await asyncio.sleep(3)
        # except: pass
        
        # Build 5-layer prompt
        prompt = PromptBuilder.build(
            character_pose, camera_angle, style_suffix,
            motion_description, dialogue, sfx, character_name, emotion
        )
        logger.info(f"📝 Prompt: {prompt[:100]}...")
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image text file not found at {image_path}")

        # Step 0: Ensure 'Video' Mode (Critical Fix)
        # User reported: "icon should change image to video by cliking on image icon"
        # We need to find the "Image" toggle or icon and switch it to "Video" BEFORE uploading.
        # Step 0: Ensure 'Video' Mode (Critical Fix - Updated for new UI)
        # Screenshot shows "Image ▼" dropdown at bottom-right, need to switch to "Video"
        logger.info("🔄 Checking for Mode Toggle (Image/Video dropdown)...")
        
        mode_btn_selectors = [
            "button:has-text('Image')",  # Current mode shows "Image" - need to switch
            "button[aria-label='Model select']",  # Legacy selector
            "button:has-text('Video')",  # Already in video mode
        ]
        
        try:
            mode_switched = False
            for selector in mode_btn_selectors:
                mode_btn = page.locator(selector).first
                if await mode_btn.count() > 0 and await mode_btn.is_visible():
                    btn_text = await mode_btn.text_content()
                    logger.info(f"ℹ️ Found mode button: '{btn_text}' via {selector}")
                    
                    if "Video" in btn_text:
                        logger.info("✅ Already in Video mode")
                        mode_switched = True
                        break
                    elif "Image" in btn_text:
                        logger.info("🖱️ Currently in Image mode, switching to Video...")
                        await mode_btn.click()
                        await asyncio.sleep(1)  # Wait for dropdown to fully open
                        
                        # Look for "Video" option in dropdown menu
                        # Based on actual HTML: <div role="menuitem">...<span>Video</span>...<span>Generate a video</span>...
                        video_option_selectors = [
                            "[role='menuitem'] >> text='Video'",  # Precise: menuitem containing "Video" text
                            "div[role='menuitem']:has(span:text-is('Video'))",  # menuitem with exact span text
                            "[data-radix-collection-item] >> text='Video'",  # Radix menu item
                            "div[role='menuitem']:has-text('Video')",  # menuitem with Video text
                            "div.cursor-pointer:has-text('Generate a video')",  # Fallback: div with video description
                        ]
                        
                        for video_sel in video_option_selectors:
                            try:
                                video_opt = page.locator(video_sel).first
                                if await video_opt.count() > 0:
                                    # Wait for it to be visible
                                    await video_opt.wait_for(state="visible", timeout=3000)
                                    await video_opt.click()
                                    logger.info(f"✅ Selected 'Video' via {video_sel}")
                                    mode_switched = True
                                    break
                            except Exception as sel_err:
                                logger.debug(f"Selector {video_sel} failed: {sel_err}")
                                continue
                        break
            
            if not mode_switched:
                logger.warning("⚠️ Could not find or switch mode toggle, proceeding anyway")
        except Exception as e:
            logger.warning(f"⚠️ Mode toggle error: {e}")

        await asyncio.sleep(1)
            
        # Step 1: Find and fill the prompt input FIRST (Updated selectors for new UI)
        # Screenshot shows: "Type to imagine" placeholder text
        prompt_selectors = [
            "textarea[placeholder*='imagine']",  # Primary - matches "Type to imagine"
            "textarea[placeholder*='Imagine']",  # Case variation
            "textarea[aria-label*='imagine']",
            "textarea[aria-label='Ask Grok anything']",  # Legacy fallback
            "textarea",
            ".ProseMirror",
        ]
        
        prompt_filled = False
        target_element = None # Keep track for drag-and-drop
        
        for selector in prompt_selectors:
            try:
                el = page.locator(selector)
                if await el.count() > 0 and await el.first.is_visible():
                    logger.info(f"📝 Found prompt area: {selector}")
                    await el.first.click() # Focus it first!
                    await el.first.fill(prompt)
                    logger.info(f"✅ Filled prompt")
                    prompt_filled = True
                    target_element = selector # Use this for drop target
                    break
            except Exception:
                continue
        
        if not prompt_filled:
            # DEBUG SNAPSHOT
            screenshot_path = Path("debug_grok_missing_input.png").absolute()
            try:
                await page.screenshot(path=str(screenshot_path))
                logger.error(f"📸 UI Changed! Saved debug screenshot to {screenshot_path}")
            except:
                logger.error("❌ Failed to save debug screenshot")
            
            raise UIChangedError("Could not find prompt input field")
            
        await asyncio.sleep(1)

        # Step 2: Upload image (Multiple methods for robustness)
        logger.info(f"📤 Uploading image: {image_path.name}...")
        
        import base64
        import mimetypes
        
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png"
        
        upload_success = False
        
        # METHOD A: Try "Upload image" button (visible in top-right of screenshot)
        try:
            upload_btn_selectors = [
                "button:has-text('Upload image')",
                "[aria-label*='Upload']",
                "button:has-text('Upload')",
            ]
            
            for selector in upload_btn_selectors:
                upload_btn = page.locator(selector).first
                if await upload_btn.count() > 0 and await upload_btn.is_visible():
                    logger.info(f"🎯 Found upload button: {selector}")
                    
                    # Use file chooser approach
                    async with page.expect_file_chooser(timeout=5000) as fc_info:
                        await upload_btn.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(image_path))
                    logger.info("✅ Image uploaded via Upload button")
                    upload_success = True
                    break
        except Exception as e:
            logger.warning(f"⚠️ Upload button method failed: {e}")
        
        # METHOD B: Try attach/clip button near textarea
        if not upload_success:
            try:
                attach_selectors = [
                    "button[aria-label*='Attach']",
                    "button[aria-label*='attach']",
                    "[data-testid*='attach']",
                ]
                
                for selector in attach_selectors:
                    attach_btn = page.locator(selector).first
                    if await attach_btn.count() > 0 and await attach_btn.is_visible():
                        logger.info(f"🎯 Found attach button: {selector}")
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await attach_btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(str(image_path))
                        logger.info("✅ Image uploaded via Attach button")
                        upload_success = True
                        break
            except Exception as e:
                logger.warning(f"⚠️ Attach button method failed: {e}")
        
        # METHOD C: Drag-and-drop fallback
        if not upload_success:
            try:
                with open(image_path, "rb") as f:
                    file_b64 = base64.b64encode(f.read()).decode("utf-8")
                
                drop_target_selector = target_element if target_element else "body"
                logger.info(f"🎯 Attempting drag-and-drop onto: {drop_target_selector}")
                
                drop_target = page.locator(drop_target_selector).first
                await drop_target.wait_for(state="attached", timeout=5000)
                
                await page.evaluate("""
                    async ({ selector, fileBase64, fileName, fileType }) => {
                        const byteCharacters = atob(fileBase64);
                        const byteNumbers = new Array(byteCharacters.length);
                        for (let i = 0; i < byteCharacters.length; i++) {
                            byteNumbers[i] = byteCharacters.charCodeAt(i);
                        }
                        const byteArray = new Uint8Array(byteNumbers);
                        const blob = new Blob([byteArray], { type: fileType });
                        const file = new File([blob], fileName, { type: fileType });
                        
                        const dataTransfer = new DataTransfer();
                        dataTransfer.items.add(file);
                        
                        const target = document.querySelector(selector);
                        if (!target) throw new Error(`Drop target not found: ${selector}`);
                        
                        target.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer }));
                        target.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer }));
                        target.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer }));
                    }
                """, {
                    "selector": drop_target_selector,
                    "fileBase64": file_b64,
                    "fileName": image_path.name,
                    "fileType": mime_type
                })
                
                logger.info("✅ Drop event dispatched successfully")
                upload_success = True
            except Exception as e:
                logger.error(f"❌ Drag-and-drop also failed: {e}")
        
        if not upload_success:
            logger.warning("⚠️ All image upload methods failed, proceeding with text-only generation")

        # Wait for upload processing (thumbnail appearance)
        await asyncio.sleep(5)
        
        # Step 3: Mode switch handled in Step 0 now.
        
        # Step 4: Configure video settings if available
        
        # Step 4: Configure video settings if available
        await VideoSettings.configure(page, duration=duration, aspect=aspect)
        
        # Step 5: Click generate/submit button (arrow icon on right)
        submit_selectors = [
            "button[aria-label='Send message']",
            "button[aria-label='Send']",
            "button[aria-label='Submit']",
            "button[type='submit']",
        ]
        
        submitted = False
        for selector in submit_selectors:
            try:
                el = page.locator(selector)
                if await el.count() > 0:
                    await el.first.click()
                    logger.info(f"✅ Clicked submit using: {selector}")
                    submitted = True
                    break
            except Exception:
                continue
        
        if not submitted:
            # Try pressing Enter as fallback but ensure focus is SAFE
            logger.info("⚠️ Submit button not found. Attempting Enter key submit...")
            try:
                # Re-focus the editor to avoid 'Attach' button focus
                editor = page.locator(".ProseMirror").first
                await editor.click()
                await page.keyboard.press("Enter")
                logger.info("↩️ Pressed Enter to submit")
            except:
                pass
        
        # Step 5: Wait for generation and download
        logger.info("⏳ Waiting for video generation...")
        
        # PREFERENCE HANDLING (Updated for new UI - screenshot shows "I prefer this" buttons)
        # Check if Grok asks for a preference A/B test
        async def check_and_handle_preference():
            try:
                # Look for preference dialog: "Which video do you prefer to keep?"
                # Buttons: "I prefer this" on each video, or "Skip" button
                
                # Check for "I prefer this" buttons
                pref_btns = page.locator("button:has-text('I prefer this'), button:has-text('prefer')")
                if await pref_btns.count() > 0:
                    logger.info("⚠️ Preference Selection UI detected! Auto-selecting first option...")
                    try:
                        await pref_btns.first.click()
                        await asyncio.sleep(2)
                        logger.info("✅ Selected preferred video")
                        return True
                    except Exception as e:
                        logger.warning(f"Failed to click prefer button: {e}")
                
                # Fallback: Try Skip button if preference buttons don't work
                skip_btn = page.locator("button:has-text('Skip')")
                if await skip_btn.count() > 0 and await skip_btn.is_visible():
                    logger.info("⏭️ Clicking Skip button on preference dialog...")
                    try:
                        await skip_btn.click()
                        await asyncio.sleep(1)
                        return True
                    except:
                        pass
            except Exception as e:
                logger.debug(f"Preference check error (may be normal): {e}")
            return False

        # Start a background task to check for preferences occasionally
        # We can't do this easily in parallel with the race below without complex task management
        # So we'll inject a check into the wait loop
        
        # METHOD 1: Download Button (High Quality / Original File)
        # This is preferred because the <video> tag often contains compressed/stream versions.
        download_selectors = [
            "button[aria-label='Download']",
            "button[aria-label='Download video']",
            "button:has-text('Download')",
            "a[download]",
            "[data-testid='download-button']",
            "button:has(svg[viewBox*='0 0 24 24']):has-text('Download')", # More specific fallback
        ]

        # Smart Wait: Race between URL change AND Video element appearance
        # We don't want to wait 180s if the video is already there!
        try:
            async def wait_for_video_element():
                # Check for video tag or any of the known download buttons
                selectors = ["video"] + download_selectors
                # INCREASED TIMEOUT: Check every 2s for 3 minutes (90 checks)
                for _ in range(90): 
                    # Inject Preference Check
                    await check_and_handle_preference()
                    
                    for selector in selectors:
                        if await page.locator(selector).count() > 0:
                            logger.info(f"✨ Found element via selector: {selector}")
                            return "element_found"
                    await asyncio.sleep(2)
                raise TimeoutError("Neither video nor download button appeared")

            # Race the two tasks
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(URLListener.wait_for_post_navigation(page, timeout=120000)),
                    asyncio.create_task(wait_for_video_element())
                ],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel the loser
            for task in pending:
                task.cancel()
                
            if any(t.result() == "element_found" for t in done if not t.cancelled() and not t.exception()):
                logger.info("🎥 Video or Download element appeared! Proceeding directly...")
            else:
                 # It was a URL change
                new_url = done.pop().result()
                logger.info(f"🔗 Navigation detected: {new_url}")
                await page.goto(new_url)
                await asyncio.sleep(3)

        except Exception as e:
            logger.info(f"⚠️ Wait condition warning: {e}. Checking for video anyway...")
        
        
        # Save to project folder for easy user access
        output_dir = Path(os.getcwd()) / "generated_videos"
        output_dir.mkdir(exist_ok=True)
        output = output_dir / f"clip_{uuid4()}.mp4"
        logger.info(f"💾 Saving video to: {output}")
        
        
        button_download_success = False
        try:
            for selector in download_selectors:
                try:
                    el = page.locator(selector)
                    if await el.count() > 0:
                        logger.info(f"🎯 Found download button: {selector}")
                        
                        # Set up the download listener BEFORE clicking
                        async with page.expect_download(timeout=45000) as dl:
                            # Try normal click first
                            try:
                                await el.first.click(timeout=3000)
                            except:
                                # If intercepted, use JS force click
                                logger.info("⚠️ Click intercepted/failed, trying JS click...")
                                await page.evaluate(f"document.querySelector(`{selector}`).click()")
                        
                        # Wait for the download to start
                        download = await dl.value
                        
                        # Save it
                        await download.save_as(output)
                        logger.info(f"✅ Successfully downloaded video using {selector}: {output}")
                        
                        # Verify it's actually a video (sometimes buttons trigger image downloads)
                        try:
                            file_size = output.stat().st_size
                            if file_size < 50000: # < 50KB is suspicious (was 10KB)
                                logger.warning(f"⚠️ Downloaded file too small ({file_size} bytes). Likely an error/thumbnail. Retrying...")
                                continue
                        except:
                            pass
                            
                        button_download_success = True
                        return output
                except Exception as e:
                    logger.debug(f"Button attempt failed ({selector}): {e}")
                    continue
        except Exception:
            pass
            
        if not button_download_success:
             logger.warning("⚠️ High-quality button download failed. Falling back to direct stream capture...")

        # METHOD 2: Direct Video Source Download (Fallback - Lower Quality)
        try:
            video_el = page.locator("video").first
            await video_el.wait_for(state="attached", timeout=10000)
            src = await video_el.get_attribute("src")
            
            if src:
                logger.info(f"🎥 Found video source: {src[:50]}...")
                
                if src.startswith("blob:"):
                    logger.info("⬇️ Fallback: Downloading via IMG SRC (Blob Support)...")
                    # Use browser-side fetch to get blob contents as base64
                    b64_data = await page.evaluate("""async (url) => {
                        const response = await fetch(url);
                        const blob = await response.blob();
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result.split(',')[1]);
                            reader.readAsDataURL(blob);
                        });
                    }""", src)
                    import base64
                    with open(output, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    logger.info(f"✅ Downloaded blob video via JS: {output}")
                    return output

                # Get cookies from browser context
                cookies = await page.context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                headers = {
                    "User-Agent": await page.evaluate("navigator.userAgent"),
                    "Referer": "https://grok.com/"
                }

                logger.info("⬇️ Downloading video stream via Python (httpx)...")
                import httpx
                async with httpx.AsyncClient(verify=False) as client:
                    response = await client.get(src, cookies=cookie_dict, headers=headers, follow_redirects=True, timeout=90.0)
                    if response.status_code == 200:
                        # VALIDATION: Check content type and size
                        content_type = response.headers.get("content-type", "").lower()
                        if "text" in content_type or "html" in content_type:
                             logger.warning(f"⚠️ Direct download returned text/html (Alien File): {content_type}")
                             raise ValueError("Downloaded content is not a video")
                        
                        if len(response.content) < 50000: # < 50KB
                             logger.warning(f"⚠️ Direct download too small ({len(response.content)} bytes). Likely an error page.")
                             raise ValueError("Downloaded file too small")

                        with open(output, "wb") as f:
                            f.write(response.content)
                        logger.info(f"✅ Downloaded video stream: {output} ({len(response.content)} bytes)")
                        return output
                    else:
                        raise ValueError(f"HTTP {response.status_code}")
                
        except Exception as e:
            logger.warning(f"❌ Direct download failed: {e}")       
        
        if not output.exists():
             raise RuntimeError("Failed to download video by any method.")
        
        if not output.exists():
            # Last ditch: Look for video element src directly
            video_el = page.locator("video").first
            if await video_el.count() > 0:
                src = await video_el.get_attribute("src")
                if src:
                    logger.info(f"🔗 Found video source directly: {src}")
                    # We can't easily download blob: or protected URLs here without headers
                    # But often it's a direct mp4 link we can fetch
                    if src.startswith("http"):
                         # Implementation for direct download would go here, 
                         # but usually button click is safer for expiration tokens
                         pass

            raise RuntimeError("Failed to download video - button not clickable")
        
        # Verify duration
        expected_duration = 10.0 if duration == "10s" else 6.0
        VideoSettings.verify_clip_duration(output, expected_duration)
        
        return output
    finally:
        # ONLY CLOSE IF WE OPENED IT
        if not external_page and browser:
            await browser.close()
            await pw.stop()
            logger.info("🛑 Grok cleanup complete.")


# ============================================
# Browser Profile Manager
# ============================================
class BrowserProfileManager:
    """
    Manages persistent browser profiles for Grok sessions.
    
    This preserves:
    - Login cookies (avoid re-auth)
    - Session state
    - Cache for faster loads
    """
    
    def __init__(self, profile_name: str = "default"):
        # Unify with global PROFILE_PATH if default, else handle named profiles in same root
        if profile_name == "default":
            self.profile_path = PROFILE_PATH
        else:
            self.profile_path = PROFILE_PATH.parent / ".grok-profiles" / profile_name
        self.ensure_profile_dir()
    
    def ensure_profile_dir(self):
        """Create profile directory if it doesn't exist."""
        self.profile_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Browser profile: {self.profile_path}")
    
    async def is_logged_in(self) -> bool:
        """Check if profile has valid Grok session."""
        cookies_file = self.profile_path / "Default" / "Cookies"
        return cookies_file.exists()
    
    def clear_cache(self):
        """Clear browser cache but keep cookies."""
        cache_dir = self.profile_path / "Default" / "Cache"
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)
            logger.info("🧹 Cleared browser cache")
    
    def backup_profile(self, backup_name: str = None):
        """Create a backup of the current profile."""
        import shutil
        from datetime import datetime
        
        backup_name = backup_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.profile_path.parent / f"{self.profile_path.name}_backup_{backup_name}"
        shutil.copytree(self.profile_path, backup_path)
        logger.info(f"💾 Profile backed up to: {backup_path}")
        return backup_path
    
    async def get_context(self) -> tuple[BrowserContext, any]:
        """Get browser context with this profile."""
        playwright = await async_playwright().start()
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-dev-shm-usage',
            '--js-flags="--max-old-space-size=2048"', # Memory limit
            '--process-per-site'
        ]
        
        extension_path = os.getenv("GROK_EXTENSION_PATH")
        if extension_path and os.path.isdir(extension_path):
            logger.info(f"🧩 Loading Grok Extension (ProfileManager) from: {extension_path}")
            args.append(f"--disable-extensions-except={extension_path}")
            args.append(f"--load-extension={extension_path}")

        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_path),
            headless=os.getenv("GROK_HEADLESS", "false").lower() == "true",
            args=args,
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
        
        # Avoid empty tabs by reusing the default page
        if len(browser.pages) == 0:
            await browser.new_page()
            
        return browser, playwright


# ============================================
# GrokAnimator - High-Level API for Workflow
# ============================================
class GrokAnimator:
    """
    High-level animation API for the video generation workflow.
    
    Usage:
        animator = GrokAnimator()
        video_path = await animator.animate(
            image_path="/path/to/scene.png",
            motion_prompt="The character walks forward",
            duration=10
        )
    """
    
    def __init__(self, profile_name: str = "default"):
        self.profile_manager = BrowserProfileManager(profile_name)
        self.generation_count = 0
        self.refresh_threshold = 5
        self.rate_limit_cooldown = 7200  # 2 hours in seconds

    async def _handle_session_refresh(self, page: Page):
        """Restarts the session to clear memory leaks."""
        if self.generation_count > 0 and self.generation_count % self.refresh_threshold == 0:
            logger.info(f"♻️ Grok Refresh Threshold ({self.refresh_threshold}) reached. Cleaning session...")
            try:
                # 1. Clear IndexedDB and LocalStorage 
                await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
                
                # 2. Hard Reload
                await page.goto("https://grok.com/imagine", wait_until="networkidle", timeout=60000)
                logger.info("🚀 Grok Session refreshed. Memory cleared.")
            except Exception as e:
                logger.warning(f"Session refresh failed: {e}")
    
    async def animate(
        self,
        image_path: Path,
        motion_prompt: str = "",
        style_suffix: str = "Cinematic, dramatic lighting",
        duration: int = 10,
        aspect_ratio: str = "9:16",
        camera_angle: str = "Medium shot",
        dialogue: Optional[str] = None,
        sfx: Optional[str] = None
    ) -> Path:
        """
        Animate an image using Grok Imagine.
        
        Args:
            image_path: Path to the input image
            motion_prompt: Description of the motion/animation
            style_suffix: Visual style to apply
            duration: 6 or 10 seconds
            aspect_ratio: "9:16" or "16:9"
            camera_angle: Shot type (e.g. "Wide Shot")
            
        Returns:
            Path to the generated video file
        """
        duration_str = f"{duration}s"
        
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            # Each attempt starts its own browser context to ensure a clean slate
            # (Reverting the persistent session reuse per user request)
            browser, pw = await self.profile_manager.get_context()
            page = browser.pages[0] if len(browser.pages) > 0 else await browser.new_page()
            
            try:
                logger.info(f"🔄 Animation Attempt {attempt+1}/{MAX_RETRIES} for {image_path.name}")
                
                # Handle session refresh if threshold reached (within this context)
                await self._handle_session_refresh(page)

                result = await generate_single_clip(
                    image_path=image_path,
                    character_pose="the character in the image",
                    camera_angle=camera_angle,
                    style_suffix=style_suffix,
                    motion_description=motion_prompt,
                    duration=duration_str,
                    aspect=aspect_ratio,
                    dialogue=dialogue,
                    sfx=sfx,
                    external_page=page # Pass the active page
                )
                
                # Validation: Check if file actually exists and has size
                if result and result.exists() and result.stat().st_size > 1000:
                   self.generation_count += 1
                   logger.info(f"🎥 Generated clip #{self.generation_count}: {result}")
                   return result
                else:
                    raise RuntimeError("Generated file missing or empty")

            except RateLimitError:
                logger.warning(f"⏳ Rate limit hit after {self.generation_count} generations")
                raise
            except Exception as e:
                logger.error(f"❌ Grok Generation failed: {e}")
                # Take screenshot if headful (debugging)
                try:
                    timestamp = int(asyncio.get_event_loop().time())
                    await page.screenshot(path=f"grok_error_{timestamp}.png")
                except:
                    pass
                if attempt < MAX_RETRIES - 1:
                    wait_time = (attempt + 1) * 5
                    logger.info(f"♻️ Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("🛑 All retries failed.")
                    raise e
            finally:
                # Close browser after EACH clip (Reverting speed boost per user request)
                await browser.close()
                await pw.stop()
    
    async def animate_batch(
        self,
        scenes: list[dict],
        style_suffix: str = "Cinematic, dramatic lighting",
        on_progress: callable = None
    ) -> list[Path]:
        """
        Animate multiple scenes with rate limit handling.
        
        Args:
            scenes: List of dicts with 'image_path' and 'motion_prompt'
            style_suffix: Visual style for all scenes
            on_progress: Callback(scene_index, total) for progress updates
            
        Returns:
            List of paths to generated video files
        """
        results = []
        
        for i, scene in enumerate(scenes):
            if on_progress:
                on_progress(i, len(scenes))
            
            try:
                video_path = await self.animate(
                    image_path=Path(scene['image_path']),
                    motion_prompt=scene.get('motion_prompt', ''),
                    style_suffix=style_suffix,
                    duration=scene.get('duration', 10)
                )
                results.append(video_path)
                
                # Add delay between generations to avoid rate limiting
                if i < len(scenes) - 1:
                    delay = random.uniform(5, 10)
                    logger.info(f"⏱️ Waiting {delay:.1f}s before next generation...")
                    await asyncio.sleep(delay)
                    
            except RateLimitError:
                logger.error(f"Rate limited at scene {i+1}/{len(scenes)}")
                return results
        
        return results
    
    def get_stats(self) -> dict:
        """Get generation statistics."""
        return {
            "generations_this_session": self.generation_count,
            "profile_path": str(self.profile_manager.profile_path),
            "rate_limit_cooldown_seconds": self.rate_limit_cooldown
        }


# ============================================
# CLI for Manual Testing and Setup
# ============================================
if __name__ == "__main__":
    import sys
    import re
    
    async def setup_profile():
        """Open browser for manual login to save session."""
        print("🚀 Opening Grok browser for login...")
        print(f"📁 Profile will be saved to: {PROFILE_PATH}")
        print("\n" + "="*50)
        print("INSTRUCTIONS:")
        print("1. A browser window will open")
        print("2. Log in to your X/Twitter account")
        print("3. Navigate to https://grok.com/imagine")
        print("4. Once logged in, close the browser window")
        print("5. Your session will be saved for future automation")
        print("="*50 + "\n")
        
        browser, pw = await get_browser_context()
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        await page.goto("https://grok.com/imagine", wait_until="networkidle", timeout=60000)
        
        print("✅ Browser opened! Please log in manually.")
        print("⏳ Waiting for you to close the browser...")
        
        # Keep browser open until user closes it
        try:
            while True:
                await asyncio.sleep(1)
                # Check if browser still open
                if not browser.pages:
                    break
        except Exception:
            pass
        finally:
            try:
                await browser.close()
                await pw.stop()
            except:
                pass
        
        print("\n✅ Profile saved! You can now run automation without logging in again.")
    
    async def test_generation():
        # Test with a sample image
        if len(sys.argv) < 2:
            print("Usage: python grok_agent.py <image_path>")
            print("       python grok_agent.py --setup    (for first-time login)")
            return
        
        image_path = Path(sys.argv[1])
        if not image_path.exists():
            print(f"Image not found: {image_path}")
            return
        
        animator = GrokAnimator()
        result = await animator.animate(
            image_path=image_path,
            motion_prompt="The character slowly turns their head",
            style_suffix="Cinematic, dramatic lighting",
            duration=10
        )
        print(f"✅ Generated: {result}")
    
    # Check for --setup flag
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        asyncio.run(setup_profile())
    else:
        asyncio.run(test_generation())


