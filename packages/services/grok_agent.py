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


class ModerationError(Exception):
    """Raised when Grok flags content as moderated."""
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
        dialogue: Optional[str | dict] = None,
        sound_effect: Optional[str] = None,
        character_name: str = "Character",
        emotion: str = "neutrally",
        grok_video_prompt: Optional[dict] = None,
        sfx: Optional[list[str]] = None,
        music_notes: Optional[str] = None
    ) -> str:
        """
        Builds the prompt in the "Director's Script" format for Grok Imagine 1.0.
        Format: [Timeline Actions] + AUDIO: [Character] (Tone): "Text" + SFX: [Effects]
        """
        
        def format_timeline(text: str) -> str:
            """Converts shorthand (0-2s) or [0-2s] to strict [00:00–00:02] format."""
            import re
            
            # Pattern for (0-2s), [0-2], (2:4), etc.
            pattern = r'[\(\[]([0-9]+)[\-–:]([0-9]+)s?[\)\]]'
            
            def replacer(match):
                start = int(match.group(1))
                end = int(match.group(2))
                return f"[{start // 60:02d}:{start % 60:02d}–{end // 60:02d}:{end % 60:02d}]"
                
            return re.sub(pattern, replacer, text)

        # 1. Base Motion / Timeline
        base_prompt = ""
        if grok_video_prompt and grok_video_prompt.get("full_prompt"):
            base_prompt = grok_video_prompt["full_prompt"]
        else:
            prompt_parts = []
            motion_core = motion_description
            if grok_video_prompt:
                if grok_video_prompt.get("main_action"):
                    motion_core = grok_video_prompt["main_action"]
                    if grok_video_prompt.get("character_animation"):
                        motion_core += f" {grok_video_prompt['character_animation']}"
            
            if motion_core: prompt_parts.append(motion_core.strip())
            if camera_angle: prompt_parts.append(f"Shot: {camera_angle}")
            if emotion and emotion.lower() != "neutrally": prompt_parts.append(f"Emotion: {emotion}")
            if style_suffix: prompt_parts.append(f"Style: {style_suffix}")
            base_prompt = ". ".join(prompt_parts)

        # Apply timeline formatting to the base prompt
        base_prompt = format_timeline(base_prompt)
        
        # 2. Synchronized AUDIO
        audio_block = ""
        if dialogue:
            tone = f"({emotion})" if emotion and emotion.lower() != "neutrally" else "(Natural)"
            
            if isinstance(dialogue, dict):
                audio_parts = []
                for char, text in dialogue.items():
                    audio_parts.append(f'[{char.upper()}] {tone}: "{text.strip()}"')
                audio_block = " AUDIO: " + " ".join(audio_parts)
            else:
                d_str = str(dialogue).strip()
                if "AUDIO:" not in base_prompt and "Dialogue" not in base_prompt:
                    # Clean up existing character names if present in string like "BOY: Hello"
                    match = re.search(r'^([^:]+):\s*"?(.+?)"?$', d_str)
                    if match:
                        char, text = match.groups()
                        audio_block = f' AUDIO: [{char.upper()}] {tone}: "{text}"'
                    else:
                        audio_block = f' AUDIO: [{character_name.upper()}] {tone}: "{d_str}"'

        # 3. Layered SFX
        sfx_block = ""
        all_sfx = []
        if sound_effect: all_sfx.append(sound_effect)
        if sfx: all_sfx.extend(sfx)
        
        if all_sfx:
            unique_sfx = list(dict.fromkeys([s for s in all_sfx if s]))
            sfx_str = ", ".join(unique_sfx)
            if "SFX:" not in base_prompt and "Sound Effect" not in base_prompt:
                sfx_block = f" SFX: {sfx_str}."

        # Final assembly
        final_prompt = base_prompt.strip()
        if audio_block: final_prompt += audio_block
        if sfx_block: final_prompt += sfx_block
        
        # Ensure it starts with the duration if not present (e.g. "6s: ")
        if not re.search(r'^[0-9]+s:', final_prompt):
             duration_prefix = "6s: " # Default to 6s for Grok Imagine
             final_prompt = duration_prefix + final_prompt

        return final_prompt


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
                # Grok URLs can be /post/, /status/, or /project/ after generation
                # CRITICAL: Ensure we stay on grok.com and avoid X.com redirects
                if current_url != original_url and \
                   "grok.com" in current_url and \
                   any(x in current_url for x in ["/post/", "/status/", "/project/"]):
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
    # Buttons may have aria-label="9:16" OR text like "Vertical"/"Landscape"
    ASPECT_SELECTORS = {
        "9:16": [
            "button[aria-label='9:16']",
            "button[aria-label*='Vertical']",
            "button[aria-label*='Portrait']",
            "[aria-label='9:16']",
            "button:has-text('9:16')",
            "button:has-text('Vertical')",
            "button:has-text('Portrait')",
            ".aspect-vertical",
            "button:has-text('9')", # Partial match fallback
            "svg:has-text('9:16')", # Sometimes it's an SVG text
            "button:has(svg[aria-label='9:16'])",
        ],
        "16:9": [
            "button[aria-label='16:9']",
            "button[aria-label*='Landscape']",
            "button[aria-label*='Horizontal']",
            "[aria-label='16:9']",
            "div[role='menuitem']:has-text('16:9')",
            "div[role='menuitem']:has(span:text-is('16:9'))",
            "button:has-text('16:9')",
            "button:has-text('Landscape')",
            "button:has-text('Horizontal')",
            ".aspect-landscape",
            "button:has-text('16')", # Partial match fallback
            "svg:has-text('16:9')",
            "button:has(svg[aria-label='16:9'])",
        ],
        "1:1": [
            "button[aria-label='1:1']",
            "button[aria-label*='Square']",
            "[aria-label='1:1']",
            "button:has-text('1:1')",
            "button:has-text('Square')",
        ],
    }
    
    @classmethod
    async def configure(cls, page: Page, duration: str = "10s", aspect: str = "9:16"):
        """Set duration and aspect ratio before generating.
        
        Grok (Feb 2026) places settings inside a Radix dropdown popup
        triggered by the #model-select-trigger button. We must:
        1. Open the popup
        2. Click duration button
        3. Click aspect ratio button
        4. Close the popup
        """
        print(f"\n{'='*50}")
        print(f"🔧 VideoSettings.configure() CALLED: duration={duration}, aspect={aspect}")
        print(f"{'='*50}\n")
        logger.info(f"⚙️ Configuring video settings: duration={duration}, aspect={aspect}")
        
        # ========================================
        # Step 1: Open the settings popup
        # ========================================
        popup_opened = False
        
        # We scan all potential "More options" buttons but filter out those inside chat bubbles/posts
        # This is more robust than trying to guess the exact composer container class
        
        popup_trigger_selectors = [
            "#model-select-trigger",
            "button[aria-label='Model select']",
            "button#model-select-trigger",
            "button[aria-label='More options']",
            "button[aria-label='Options']",
            "button:has(svg)", # Generic fallback
        ]
        
        for sel in popup_trigger_selectors:
            try:
                # Get ALL matching buttons
                elements = await page.locator(sel).all()
                # Iterate in reverse to prioritize the bottom-most one (usually the composer)
                for trigger in reversed(elements):
                    if await trigger.is_visible():
                        # CRITICAL: Check if it's inside a conversation bubble/post
                        # This prevents clicking "More options" on a previously generated video
                        is_in_bubble = await trigger.evaluate("""el => {
                            return !!el.closest('[data-testid="post-bubble"]') || 
                                   !!el.closest('article') || 
                                   !!el.closest('.chat-bubble') ||
                                   !!el.closest('[data-testid="tweetText"]')
                        }""")
                        
                        if is_in_bubble:
                            # logger.debug(f"⏭️ Skipping {sel} because it is inside a chat bubble")
                            continue
                            
                        await trigger.click()
                        await asyncio.sleep(1)  # Wait for Radix popup animation
                        
                        # Verify popup actually opened (look for Duration/Aspect buttons)
                        if await page.locator("text='Aspect Ratio'").count() > 0 or \
                           await page.locator("text='Duration'").count() > 0 or \
                           await page.locator("button:has-text('9:16')").count() > 0:
                            popup_opened = True
                            logger.info(f"📂 Opened settings popup via: {sel}")
                            break
                        else:
                             # If click didn't open settings, maybe try next button
                             logger.debug(f"⚠️ Clicked {sel} but settings popup didn't appear")
                
                if popup_opened: break
            except Exception as e:
                continue
        
        if not popup_opened:
            logger.warning("⚠️ Could not open settings popup, trying direct button clicks as fallback...")
            # Desperate Step 1b: Force click "More options" ONLY if in composer (Feb 2026 workaround)
            try:
                more_opts = page.locator(f"{composer_sel} button[aria-label='More options']").last
                if await more_opts.count() > 0:
                    await more_opts.click(force=True)
                    await asyncio.sleep(1.5) # Wait for menu
                    popup_opened = True
                    logger.info("📂 Force-clicked composer 'More options' as fallback")
            except Exception as e:
                logger.warning(f"⚠️ Composer 'More options' fallback failed: {e}")
        
        # ========================================
        # Step 2: Set duration inside the popup
        # ========================================
        duration_clicked = False
        # Popup buttons use aria-label="6s" / aria-label="10s"
        duration_selectors = [
            f"button[aria-label='{duration}']",
            *cls.DURATION_SELECTORS.get(duration, []),
        ]
        for selector in duration_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    logger.info(f"✅ Set duration: {duration} via {selector}")
                    duration_clicked = True
                    break
            except Exception:
                continue
        
        if not duration_clicked:
            logger.warning(f"⚠️ Could not set duration: {duration}")
        
        # ========================================
        # Step 3: Set aspect ratio inside the popup
        # ========================================
        aspect_clicked = False
        # Popup buttons use aria-label="16:9", aria-label="9:16", etc.
        aspect_selectors = [
            f"button[aria-label='{aspect}']",
            *cls.ASPECT_SELECTORS.get(aspect, []),
        ]
        for selector in aspect_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    try:
                        await btn.click()
                    except Exception:
                        await page.evaluate("(sel) => document.querySelector(sel)?.click()", selector)
                    logger.info(f"✅ Set aspect ratio: {aspect} via {selector}")
                    aspect_clicked = True
                    break
            except Exception as e:
                logger.debug(f"Aspect selector {selector} failed: {e}")
                continue

        if not aspect_clicked:
            # Last resort: scan all visible buttons for matching aria-label
            logger.warning(f"⚠️ Primary selectors failed for aspect={aspect}, scanning all buttons...")
            try:
                all_btns = await page.locator("button").all()
                for btn in all_btns:
                    try:
                        label = (await btn.get_attribute("aria-label") or "")
                        if label == aspect and await btn.is_visible():
                            await btn.click()
                            logger.info(f"✅ Set aspect ratio (scan): {aspect}")
                            aspect_clicked = True
                            break
                    except: continue
            except Exception as e:
                logger.error(f"Button scan failed: {e}")
        
        if not aspect_clicked:
            print(f"\n{'='*60}")
            print(f"⚠️ ASPECT RATIO BUTTON NOT FOUND: {aspect}")
            print(f"{'='*60}")
            try:
                if not page.is_closed():
                    buttons = await page.locator("button").all()
                    print(f"Total buttons on page: {len(buttons)}")
                    for i, b in enumerate(buttons[:40]):
                        try:
                            label = await b.get_attribute("aria-label") or ""
                            text = (await b.text_content() or "").strip()[:80]
                            visible = await b.is_visible()
                            print(f"  Button[{i}]: aria='{label}' text='{text}' visible={visible}")
                        except:
                            print(f"  Button[{i}]: <error reading>")
            except Exception as e:
                print(f"  Error listing buttons: {e}")
            print(f"{'='*60}\n")
            
            # Save diagnostic screenshot
            try:
                screenshot_path = Path(os.getcwd()) / f"grok_error_{random.randint(1000,99999)}.png"
                if not page.is_closed():
                    await page.screenshot(path=str(screenshot_path))
                    print(f"📸 Diagnostic screenshot saved: {screenshot_path}")
            except: pass
            logger.warning(f"⚠️ Could not find aspect ratio button for {aspect}.")
        
        # ========================================
        # Step 4: Close the popup (press Escape)
        # ========================================
        if popup_opened:
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                logger.info("📂 Closed settings popup")
            except:
                pass

    
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


async def _clean_grok_locks(profile_path: Path = PROFILE_PATH):
    """Removes Singleton lock files without killing all chrome processes."""
    # Aggressive taskkill removed to prevent killing companion agents (Whisk)
    # Browsers should manage themselves; we only clean the profile filesystem locks
    locks = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
    for lock in locks:
        lock_path = profile_path / lock
        if lock_path.exists():
            try:
                lock_path.unlink()
                logger.info(f"🧹 Removed stale Grok lock: {lock}")
            except: pass


# ============================================
# Browser Management
# ============================================
async def get_browser_context(playwright: any) -> BrowserContext:
    """Create browser context with persistent profile."""
    # LOCK HANDLING: The caller should already hold the _grok_lock
    args = [
        '--disable-blink-features=AutomationControlled', 
        '--no-sandbox', 
        '--disable-infobars'
    ]
    
    ext_path_str = os.getenv("GROK_EXTENSION_PATH")
    if ext_path_str:
        ext_paths = [p.strip() for p in ext_path_str.split(',') if os.path.isdir(p.strip())]
        if ext_paths:
            logger.info(f"🧩 Loading {len(ext_paths)} Grok Extensions...")
            load_arg = ",".join(ext_paths)
            args.append(f"--disable-extensions-except={load_arg}")
            args.append(f"--load-extension={load_arg}")

    MAX_RETRIES = 5
    for attempt in range(MAX_RETRIES):
        try:
            return await playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_PATH),
                headless=False,
                accept_downloads=True,
                ignore_default_args=["--enable-automation"],
                args=args,
                viewport={'width': 1100, 'height': 800}
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "target page, context or browser has been closed" in error_msg or "existing browser session" in error_msg or "in use" in error_msg:
                logger.warning(f"⚠️ Grok Browser Lock (Attempt {attempt+1}/{MAX_RETRIES}). Cleaning locks...")
                await _clean_grok_locks()
                await asyncio.sleep(2 * (attempt + 1))
            else:
                raise e
    
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
    sound_effect: Optional[str] = None,
    character_name: str = "Character",
    emotion: str = "neutrally",
    duration: str = "10s",
    aspect: str = "9:16",
    external_page: Optional[Page] = None,
    grok_video_prompt: Optional[dict] = None,
    sfx: Optional[list[str]] = None,
    music_notes: Optional[str] = None
) -> Path:
    browser = None
    pw = None
    page = external_page
    
    # helper session context
    class GrokLocalSession:
        def __init__(self, agent_lock):
            self.lock = agent_lock
            self.entered = False
        async def __aenter__(self):
            if not external_page:
                await self.lock.acquire()
                self.entered = True
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.entered:
                self.lock.release()

    async with GrokLocalSession(_grok_lock):
        if not page:
            pw = await async_playwright().start()
            try:
                browser = await get_browser_context(pw)
                page = browser.pages[0] if browser.pages else await browser.new_page()
            except Exception as e:
                if pw: await pw.stop()
                raise e
    
        try:
            # await Stealth().apply_stealth_async(page)  <-- DISABLED to match login script
            await page.goto("https://grok.com/imagine", wait_until="networkidle", timeout=60000)
            
            # Wait for page to fully load
            await asyncio.sleep(3)
            
            # Check rate limit FIRST
            if await check_rate_limit(page):
                raise RateLimitError("Rate limit detected")

            # Check for "Start a conversation" or "Project" dashboard that blocks Imagine
            if await page.locator("text='Start a conversation in this project'").count() > 0 or "/project/" in page.url:
                logger.warning("📍 Detected Project Dashboard instead of Imagine view. Attempting to force Imagine mode...")
                
                # Check for "Imagine" sidebar item first as it's more reliable than goto
                sidebar_imagine = page.locator("a[aria-label='Imagine'], button:has-text('Imagine'), a:has-text('Imagine')").first
                if await sidebar_imagine.count() > 0 and await sidebar_imagine.is_visible():
                    logger.info("🖱️ Clicking 'Imagine' in sidebar...")
                    await sidebar_imagine.click()
                    await asyncio.sleep(2)
                
                if "/imagine" not in page.url:
                    await page.goto("https://grok.com/imagine", wait_until="networkidle")
                    await asyncio.sleep(3)

            # Build 5-layer prompt
            prompt = PromptBuilder.build(
                character_pose, camera_angle, style_suffix,
                motion_description, dialogue,
                character_name=character_name, emotion=emotion, sound_effect=sound_effect,
                grok_video_prompt=grok_video_prompt,
                sfx=sfx,
                music_notes=music_notes
            )
            # LOG FULL PROMPT (User Request)
            print(f"\n{'*'*60}")
            print(f"🚀 FULL GROK PROMPT:\n{prompt}")
            print(f"{'*'*60}\n")
            logger.info(f"📝 Prompt length: {len(prompt)} chars")
            
            if not image_path.exists():
                raise FileNotFoundError(f"Image text file not found at {image_path}")

            # Step 0: Ensure 'Video' Mode (Critical Fix)
            # Screenshot shows "Image ▼" dropdown at bottom-right, need to switch to "Video"
            logger.info("🔄 Checking for Mode Toggle (Image/Video dropdown)...")
            
            composer_sel = "div:has(textarea), [role='main'] div.sticky, [role='main'] div.fixed, div.composer"
            
            mode_btn_selectors = [
                f"{composer_sel} button:has-text('Image')",
                f"{composer_sel} button[aria-label='Model select']",
                f"{composer_sel} button:has-text('Video')",
                # Fallbacks if composer scoping fails
                "button:has-text('Image')",
                "button:has-text('Video')",
            ]
            
            target_element = None # Keep track for drag-and-drop
            try:
                mode_switched = False
                for selector in mode_btn_selectors:
                    mode_btn = page.locator(selector).last 
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
                            video_option_selectors = [
                                "[role='menuitem'] >> text='Video'",
                                "div[role='menuitem']:has(span:text-is('Video'))",
                                "[data-radix-collection-item] >> text='Video'",
                                "div[role='menuitem']:has-text('Video')",
                                "div.cursor-pointer:has-text('Generate a video')",
                            ]
                            
                            for video_sel in video_option_selectors:
                                try:
                                    video_opt = page.locator(video_sel).first
                                    if await video_opt.count() > 0 and await video_opt.is_visible():
                                        await video_opt.click()
                                        logger.info(f"✅ Selected Video mode via {video_sel}")
                                        mode_switched = True
                                        await asyncio.sleep(1)
                                        break
                                except: pass
                            if mode_switched: break
                
                if not mode_switched:
                    logger.warning("⚠️ Could not confirm Video mode toggle via dropdown, continuing anyway...")
            except Exception as e:
                logger.warning(f"⚠️ Error during mode toggle: {e}")

            # Step 1: Find and fill the prompt input
            prompt_selectors = [
                "textarea[placeholder*='imagine']",
                "textarea[placeholder*='Imagine']",
                "textarea[aria-label*='imagine']",
                "textarea[aria-label='Ask Grok anything']",
                "textarea",
                ".ProseMirror",
            ]
            
            prompt_filled = False
            for selector in prompt_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0 and await el.is_visible():
                        logger.info(f"📝 Found prompt area: {selector}")
                        await el.click()
                        await el.fill(prompt)
                        logger.info("✅ Filled prompt")
                        prompt_filled = True
                        target_element = selector
                        break
                except: continue
            
            if not prompt_filled:
                raise UIChangedError("Could not find prompt input field")

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
                "button:has(span.sr-only:text-is('Download image'))", # Very specific per user HTML
                "button:has(svg.lucide-download)", # Specific icon class
                "a[download]", 
                "[data-testid='download-button']",
            ]

            # CRITICAL: Auto-close X.com/Twitter popups to prevent "Share" misclicks
            async def handle_popup(popup):
                try:
                    url = popup.url
                    if "x.com" in url or "twitter.com" in url:
                        logger.warning(f"🚫 Blocking X/Twitter popup: {url}")
                        await popup.close()
                except: pass
            
            page.on("popup", lambda p: asyncio.create_task(handle_popup(p)))

            # Smart Wait: Checking for Video element appearance ONLY
            # Disabled URLListener race because Grok's new UI doesn't reliably redirect to /post/
            try:
                result = await wait_for_video_element()
                
                if result == "element_found":
                    logger.info("🎥 Video or Download element appeared! Proceeding directly...")
               
            except Exception as e:
                logger.info(f"⚠️ Wait condition warning: {e}. Checking for video anyway...")
            
            
            # Save to project folder for easy user access
            output_dir = Path(os.getcwd()) / "generated_videos"
            output_dir.mkdir(exist_ok=True)
            output = output_dir / f"clip_{uuid4()}.mp4"
            logger.info(f"💾 Saving video to: {output}")
            
            if page.is_closed():
                raise RuntimeError("Browser closed before download could start")

            button_download_success = False
            try:
                # TRY BUTTONS WITH RETRIES (to handle "not ready on backend" case)
                for selector in download_selectors:
                    if page.is_closed(): break
                    
                    for attempt in range(3): # Try each button up to 3 times with delays
                        if page.is_closed(): break
                        try:
                            el = page.locator(selector).first
                            if await el.count() > 0:
                                if attempt == 0:
                                    logger.info(f"🎯 Found download button: {selector}")
                                else:
                                    logger.info(f"♻️ Retrying download button: {selector} (Attempt {attempt+1})")
                                
                                # Set up the download listener BEFORE clicking
                                try:
                                    async with page.expect_download(timeout=30000) as dl:
                                        # Try normal click first
                                        try:
                                            await el.click(timeout=3000)
                                        except:
                                            # If intercepted, use JS force click
                                            await page.evaluate(f"document.querySelector(`{selector}`).click()")
                                    
                                    # Wait for the download to start
                                    download = await dl.value
                                    
                                    # Save it
                                    await download.save_as(output)
                                except Exception as e:
                                    logger.debug(f"Download trigger failed: {e}")
                                    await asyncio.sleep(5)
                                    continue
                                
                                # Verify it's actually a video
                                if output.exists():
                                    file_size = output.stat().st_size
                                    
                                    # Verify it's not HTML
                                    is_html = False
                                    try:
                                        with open(output, "rb") as f:
                                            header = f.read(100)
                                            if b"<!DOCTYPE html>" in header or b"<html" in header:
                                                is_html = True
                                    except: pass

                                    if file_size < 15000 or is_html: # < 15KB or HTML is suspicious
                                        logger.warning(f"⚠️ Downloaded file is invalid (Size: {file_size}b, HTML: {is_html}). Waiting and retrying...")
                                        try: output.unlink() 
                                        except: pass
                                        await asyncio.sleep(8) # Wait for backend sync
                                        continue
                                    
                                    logger.info(f"✅ Successfully downloaded video using {selector}: {output}")
                                    button_download_success = True
                                    return output
                        except Exception as e:
                            logger.debug(f"Button attempt failed ({selector}): {e}")
                            break # Move to next selector if error isn't retryable
            except Exception:
                pass
                
            if not button_download_success:
                 logger.warning("⚠️ All high-quality buttons failed or returned invalid files. Falling back to direct stream capture...")

            # METHOD 2: Direct Video Source Download (Fallback - Lower Quality)
            try:
                if not page.is_closed():
                    video_el = page.locator("video").first
                    # Use a short timeout for fallback
                    try:
                        await video_el.wait_for(state="attached", timeout=5000)
                    except: pass
                    
                    if await video_el.count() > 0:
                        src = await video_el.get_attribute("src")
                        
                        if src:
                            logger.info(f"🎥 Found video source: {src[:50]}...")
                            
                            if src.startswith("blob:"):
                                logger.info("⬇️ Fallback: Downloading via IMG SRC (Blob Support)...")
                                # Use browser-side fetch
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
                                response = await client.get(src, cookies=cookie_dict, headers=headers, follow_redirects=True, timeout=60.0)
                                if response.status_code == 200:
                                    # Validate content type and headers to catch HTML error pages
                                    content_type = response.headers.get("content-type", "")
                                    is_html = "text/html" in content_type or b"<!DOCTYPE html>" in response.content[:500] or b"<html" in response.content[:500]
                                    
                                    if is_html:
                                        logger.warning(f"⚠️ [Method 2] Downloaded file detected as HTML (likely error page). Rejecting.")
                                        # Not in a loop here, so raise exception to trigger outer retry
                                        raise RuntimeError("Downloaded file is HTML error page")

                                    if len(response.content) < 5000:
                                        logger.warning(f"⚠️ [Method 2] Downloaded file too small ({len(response.content)} bytes). Rejecting.")
                                        raise RuntimeError("Downloaded file too small")

                                    with open(output, "wb") as f:
                                        f.write(response.content)
                                    logger.info(f"✅ Downloaded video stream: {output} ({len(response.content)} bytes)")
                                    return output
                                else:
                                    logger.warning(f"HTTP {response.status_code} on video stream download")
                            
            except Exception as e:
                logger.warning(f"❌ Direct download failed: {e}")       
            
            if not output.exists():
                # Last ditch: Look for video element src directly
                if not page.is_closed():
                    video_el = page.locator("video").first
                    if await video_el.count() > 0:
                        src = await video_el.get_attribute("src")
                        if src:
                            logger.info(f"🔗 Found video source directly: {src}")

                raise RuntimeError("Failed to download video - button not clickable or page closed")
            
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
# Atomic Scene Generator (I2V + T2V)
# ============================================
async def generate_full_scene_sequence(
    image_path: Path,
    character_pose: str,
    camera_angle: str,
    style_suffix: str,
    motion_description: str,
    t2v_prompt: Optional[str] = None,
    dialogue: Optional[str] = None,
    sound_effect: Optional[str] = None,
    character_name: str = "Character",
    emotion: str = "neutrally",
    duration: str = "10s",
    aspect: str = "9:16",
    grok_video_prompt: Optional[dict] = None,
    sfx: Optional[list[str]] = None,
    music_notes: Optional[str] = None
) -> dict:
    """
    Generate both Image-to-Video and optional Text-to-Video clips sequentially
    within a SINGLE browser session and lock.
    
    This prevents race conditions where Scene N+1 starts generating while Scene N
    is still doing its T2V step.
    """
    browser = None
    pw = None
    
    # We acquire the lock ONCE for the whole sequence
    async with _grok_lock:
        logger.info(f"🔒 Acquired lock for full scene sequence (I2V + T2V)")
        
        # Part 1: Image-to-Video
        i2v_path = None
        MAX_RETRIES = 3
        
        for attempt in range(MAX_RETRIES):
            browser = None
            pw = None
            try:
                if attempt > 0:
                    logger.info(f"♻️ I2V Retry Attempt {attempt+1}/{MAX_RETRIES}...")
                    await asyncio.sleep(5)
                
                pw = await async_playwright().start()
                browser = await get_browser_context(pw)
                page = browser.pages[0] if browser.pages else await browser.new_page()
                
                logger.info("🎬 [Sequence] Starting I2V generation...")
                i2v_path = await generate_single_clip(
                    image_path=image_path,
                    character_pose=character_pose,
                    camera_angle=camera_angle,
                    style_suffix=style_suffix,
                    motion_description=motion_description,
                    dialogue=dialogue,
                    sound_effect=sound_effect,
                    character_name=character_name,
                    emotion=emotion,
                    duration=duration,
                    aspect=aspect,
                    external_page=page,
                    grok_video_prompt=grok_video_prompt,
                    sfx=sfx,
                    music_notes=music_notes
                )
                
                # Success! Break loop
                break 
                
            except Exception as e:
                logger.error(f"❌ I2V Generation failed (Attempt {attempt+1}): {e}")
                if attempt == MAX_RETRIES - 1:
                    if browser: await browser.close()
                    if pw: await pw.stop()
                    raise e # Fail sequence if I2V fails
            finally:
                # ALWAYS close browser after I2V to ensure fresh state for T2V
                try:
                    if page and not page.is_closed():
                        await page.goto("about:blank")
                except: pass
                
                if browser: await browser.close()
                if pw: await pw.stop()
                browser = None
                pw = None
        
        # Part 2: Text-to-Video (if requested)
        t2v_path = None
        if t2v_prompt:
             for attempt in range(MAX_RETRIES):
                browser = None
                pw = None
                try:
                    logger.info("🎵 [Sequence] Starting T2V generation (Fresh Session)...")
                    if attempt > 0:
                        await asyncio.sleep(5)

                    pw = await async_playwright().start()
                    browser = await get_browser_context(pw)
                    page = browser.pages[0] if browser.pages else await browser.new_page()
                    
                    t2v_path = await generate_text_to_video_clip(
                        prompt=t2v_prompt,
                        duration=duration,
                        aspect=aspect,
                        external_page=page
                    )
                    break # Success
                    
                except Exception as e:
                    logger.error(f"❌ T2V Generation failed: {e}")
                    if attempt == MAX_RETRIES - 1:
                        # If T2V fails after all retries, we still return the valid I2V
                        logger.warning("⚠️ T2V failed all retries, returning partial result.")
                finally:
                    try:
                        if page and not page.is_closed():
                            await page.goto("about:blank")
                    except: pass

                    if browser: await browser.close()
                    if pw: await pw.stop()

        return {
            "video_path": i2v_path,
            "t2v_path": t2v_path
        }

    logger.info("🔓 Released lock for full scene sequence")


# ============================================
# Text-to-Video Generation (No Image Upload)
# ============================================
async def generate_text_to_video_clip(
    prompt: str,
    duration: str = "10s",
    aspect: str = "9:16",
    external_page: Optional[Page] = None,
) -> Path:
    """
    Generate a video from text prompt only (no image upload).
    Same flow as generate_single_clip but skips image upload
    and clicks the up-arrow submit button to start generation.
    Used as audio source for the final scene video.
    """
    browser = None
    pw = None
    page = external_page

    class GrokLocalSession:
        def __init__(self, agent_lock):
            self.lock = agent_lock
            self.entered = False
        async def __aenter__(self):
            if not external_page:
                await self.lock.acquire()
                self.entered = True
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.entered:
                self.lock.release()

    async with GrokLocalSession(_grok_lock):
        if not page:
            pw = await async_playwright().start()
            try:
                browser = await get_browser_context(pw)
                page = browser.pages[0] if browser.pages else await browser.new_page()
            except Exception as e:
                if pw: await pw.stop()
                raise e

        try:
            await page.goto("https://grok.com/imagine", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)

            if await check_rate_limit(page):
                raise RateLimitError("Rate limit detected")

            # Handle Project Dashboard redirect
            if await page.locator("text='Start a conversation in this project'").count() > 0 or "/project/" in page.url:
                logger.warning("📍 Detected Project Dashboard. Forcing Imagine mode...")
                sidebar_imagine = page.locator("a[aria-label='Imagine'], button:has-text('Imagine'), a:has-text('Imagine')").first
                if await sidebar_imagine.count() > 0 and await sidebar_imagine.is_visible():
                    await sidebar_imagine.click()
                    await asyncio.sleep(2)
                if "/imagine" not in page.url:
                    await page.goto("https://grok.com/imagine", wait_until="networkidle")
                    await asyncio.sleep(3)

            # Step 0: Ensure Video mode
            logger.info("🔄 [T2V] Checking for Mode Toggle...")
            
            # Use filtering approach instead of strict scoping
            mode_btn_selectors = [
                "button:has-text('Image')",
                "button[aria-label='Model select']",
                "button:has-text('Video')",
            ]
            
            try:
                mode_switched = False
                for selector in mode_btn_selectors:
                    # Get ALL matching buttons
                    elements = await page.locator(selector).all()
                    
                    # Iterate in reverse to prioritize the bottom-most one (usually the composer)
                    for mode_btn in reversed(elements):
                        if await mode_btn.is_visible():
                            # Check if it's inside a conversation bubble/post
                            is_in_bubble = await mode_btn.evaluate("""el => {
                                return !!el.closest('[data-testid="post-bubble"]') || 
                                       !!el.closest('article') || 
                                       !!el.closest('.chat-bubble') ||
                                       !!el.closest('[data-testid="tweetText"]')
                            }""")
                            
                            if is_in_bubble:
                                continue

                            btn_text = await mode_btn.text_content()
                            if "Video" in btn_text:
                                logger.info("✅ [T2V] Already in Video mode")
                                mode_switched = True
                                break
                            elif "Image" in btn_text:
                                logger.info("🖱️ [T2V] Switching to Video mode...")
                                await mode_btn.click()
                                await asyncio.sleep(1)
                        elif "Image" in btn_text:
                            logger.info("🖱️ [T2V] Switching to Video mode...")
                            await mode_btn.click()
                            await asyncio.sleep(1)
                            video_option_selectors = [
                                "[role='menuitem'] >> text='Video'",
                                "div[role='menuitem']:has(span:text-is('Video'))",
                                "[data-radix-collection-item] >> text='Video'",
                                "div[role='menuitem']:has-text('Video')",
                                "div.cursor-pointer:has-text('Generate a video')",
                            ]
                            for video_sel in video_option_selectors:
                                try:
                                    video_opt = page.locator(video_sel).first
                                    if await video_opt.count() > 0 and await video_opt.is_visible():
                                        await video_opt.click()
                                        logger.info(f"✅ [T2V] Selected Video mode via {video_sel}")
                                        mode_switched = True
                                        await asyncio.sleep(1)
                                        break
                                except: pass
                            if mode_switched: break
                if not mode_switched:
                    logger.warning("⚠️ [T2V] Could not confirm Video mode, continuing anyway...")
            except Exception as e:
                logger.warning(f"⚠️ [T2V] Error during mode toggle: {e}")

            # Step 1: Fill prompt
            prompt_selectors = [
                "textarea[placeholder*='imagine']",
                "textarea[placeholder*='Imagine']",
                "textarea[aria-label*='imagine']",
                "textarea[aria-label='Ask Grok anything']",
                "textarea",
                ".ProseMirror",
            ]
            prompt_filled = False
            for selector in prompt_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0 and await el.is_visible():
                        logger.info(f"📝 [T2V] Found prompt area: {selector}")
                        await el.click()
                        await el.fill(prompt)
                        logger.info("✅ [T2V] Filled prompt")
                        prompt_filled = True
                        break
                except: continue
            if not prompt_filled:
                raise UIChangedError("Could not find prompt input field")

            # Step 2: NO IMAGE UPLOAD - Skip this step entirely
            logger.info("⏩ [T2V] Skipping image upload (text-to-video mode)")

            # Step 3: Configure video settings
            await VideoSettings.configure(page, duration=duration, aspect=aspect)

            # Step 4: Click the up-arrow submit button to start generation
            logger.info("🖱️ [T2V] Clicking submit button (up-arrow)...")
            submit_selectors = [
                # Up-arrow submit button (circular button with arrow SVG)
                "div.aspect-square.rounded-full.bg-button-filled",
                "div.rounded-full.bg-button-filled",
                # Standard submit selectors
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
                        first_el = el.first
                        if await first_el.is_visible():
                            await first_el.click()
                            logger.info(f"✅ [T2V] Clicked submit using: {selector}")
                            submitted = True
                            break
                except Exception:
                    continue
            if not submitted:
                # Fallback: Enter key
                logger.info("⚠️ [T2V] Submit button not found. Trying Enter key...")
                try:
                    editor = page.locator(".ProseMirror").first
                    await editor.click()
                    await page.keyboard.press("Enter")
                    logger.info("↩️ [T2V] Pressed Enter to submit")
                except:
                    pass

            # Step 5: Wait for generation and download (same as generate_single_clip)
            logger.info("⏳ [T2V] Waiting for video generation...")

            # Preference handling
            async def check_and_handle_preference():
                try:
                    pref_btns = page.locator("button:has-text('I prefer this'), button:has-text('prefer')")
                    if await pref_btns.count() > 0:
                        logger.info("⚠️ [T2V] Preference Selection detected! Auto-selecting first...")
                        try:
                            await pref_btns.first.click()
                            await asyncio.sleep(2)
                            return True
                        except: pass
                    skip_btn = page.locator("button:has-text('Skip')")
                    if await skip_btn.count() > 0 and await skip_btn.is_visible():
                        try:
                            await skip_btn.click()
                            await asyncio.sleep(1)
                            return True
                        except: pass
                except: pass
                return False

            download_selectors = [
                "button[aria-label='Download']",
                "button[aria-label='Download video']",
                "button:has-text('Download')",
                "a[download]",
                "[data-testid='download-button']",
            ]

            try:
                async def wait_for_video_element():
                    selectors = ["video"] + download_selectors
                    generating_indicators = [
                        "Generating...", "Generating video...",
                        "Thinking...", "Drawing...",
                        "[role='progressbar']", ".animate-pulse"
                    ]
                    for i in range(150):
                        if page.is_closed():
                            raise RuntimeError("Browser closed during wait")
                        await check_and_handle_preference()
                        still_generating = False
                        for ind in generating_indicators:
                            try:
                                count = 0
                                if "[" in ind or "." in ind:
                                    count = await page.locator(ind).count()
                                else:
                                    count = await page.get_by_text(ind, exact=False).count()
                                if count > 0:
                                    still_generating = True
                                    if i % 10 == 0:
                                        logger.info(f"⏳ [T2V] Still generating (indicator: {ind})...")
                                    break
                            except: continue
                        if still_generating:
                            await asyncio.sleep(2)
                            continue
                        for selector in selectors:
                            try:
                                el = page.locator(selector).first
                                if await el.count() > 0:
                                    if selector == "video":
                                        src = await el.get_attribute("src")
                                        if not src or len(src) < 5: continue
                                    logger.info(f"✨ [T2V] Found ready element: {selector}")
                                    return "element_found"
                            except: continue
                        await asyncio.sleep(2)
                    raise TimeoutError("[T2V] Video not ready after 5 mins")

                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(URLListener.wait_for_post_navigation(page, timeout=180000)),
                        asyncio.create_task(wait_for_video_element())
                    ],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                result = None
                for t in done:
                    if not t.cancelled():
                        try: result = t.result()
                        except: result = None
                        break
                if result == "element_found":
                    logger.info("🎥 [T2V] Video element appeared!")
                elif result and ("http" in result or "/post/" in result):
                    new_url = result
                    logger.info(f"🔗 [T2V] Navigation detected: {new_url}")
                    if not page.is_closed():
                        await page.goto(new_url)
                        await asyncio.sleep(5)
            except Exception as e:
                logger.info(f"⚠️ [T2V] Wait warning: {e}. Checking for video anyway...")

            # Download the video
            output_dir = Path(os.getcwd()) / "generated_videos"
            output_dir.mkdir(exist_ok=True)
            output = output_dir / f"t2v_clip_{uuid4()}.mp4"
            logger.info(f"💾 [T2V] Saving video to: {output}")

            if page.is_closed():
                raise RuntimeError("Browser closed before download")

            button_download_success = False
            try:
                for selector in download_selectors:
                    if page.is_closed(): break
                    try:
                        el = page.locator(selector)
                        if await el.count() > 0:
                            first_btn = el.first
                            if await first_btn.is_visible():
                                async with page.expect_download(timeout=30000) as download_info:
                                    await first_btn.click()
                                download = await download_info.value
                                await download.save_as(str(output))
                                logger.info(f"✅ [T2V] Downloaded via button: {selector}")
                                button_download_success = True
                                break
                    except: continue
            except Exception as e:
                logger.warning(f"⚠️ [T2V] Button download failed: {e}")

            # Fallback: video src download
            if not button_download_success and not output.exists():
                try:
                    if not page.is_closed():
                        video_elements = await page.locator("video").all()
                        for ve in video_elements:
                            src = await ve.get_attribute("src")
                            if not src or len(src) < 10: continue
                            logger.info(f"🔗 [T2V] Trying video src: {src[:60]}...")
                            if src.startswith("blob:"):
                                b64_data = await page.evaluate("""async (src) => {
                                    const resp = await fetch(src);
                                    const blob = await resp.blob();
                                    return new Promise((resolve) => {
                                        const reader = new FileReader();
                                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                        reader.readAsDataURL(blob);
                                    });
                                }""", src)
                                import base64
                                with open(output, "wb") as f:
                                    f.write(base64.b64decode(b64_data))
                                logger.info(f"✅ [T2V] Downloaded blob video via JS")
                                break
                            cookies = await page.context.cookies()
                            cookie_dict = {c['name']: c['value'] for c in cookies}
                            headers = {
                                "User-Agent": await page.evaluate("navigator.userAgent"),
                                "Referer": "https://grok.com/"
                            }
                            import httpx
                            async with httpx.AsyncClient(verify=False) as client:
                                response = await client.get(src, cookies=cookie_dict, headers=headers, follow_redirects=True, timeout=60.0)
                                if response.status_code == 200:
                                    # Validate content type and headers to catch HTML error pages
                                    content_type = response.headers.get("content-type", "")
                                    is_html = "text/html" in content_type or b"<!DOCTYPE html>" in response.content[:500] or b"<html" in response.content[:500]
                                    
                                    if is_html:
                                        logger.warning(f"⚠️ [T2V] Downloaded file detected as HTML (likely error page). Rejecting.")
                                        continue # Try next video element

                                    if len(response.content) < 5000:
                                        logger.warning(f"⚠️ [T2V] Downloaded file too small ({len(response.content)} bytes). Rejecting.")
                                        continue # Try next video element

                                    with open(output, "wb") as f:
                                        f.write(response.content)
                                    logger.info(f"✅ [T2V] Downloaded video stream ({len(response.content)} bytes)")
                                    break
                except Exception as e:
                    logger.warning(f"❌ [T2V] Direct download failed: {e}")

            if not output.exists():
                raise RuntimeError("[T2V] Failed to download video")

            expected_duration = 10.0 if duration == "10s" else 6.0
            VideoSettings.verify_clip_duration(output, expected_duration)

            return output
        finally:
            if not external_page and browser:
                await browser.close()
                await pw.stop()
                logger.info("🛑 [T2V] Grok cleanup complete.")


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
        """Get browser context with this profile (resilient)."""
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

        MAX_RETRIES = 5
        for attempt in range(MAX_RETRIES):
            try:
                browser = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_path),
                    headless=os.getenv("GROK_HEADLESS", "false").lower() == "true",
                    args=args,
                    viewport={'width': 1100, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
                )
                
                # Avoid empty tabs by reusing the default page
                if len(browser.pages) == 0:
                    await browser.new_page()
                    
                return browser, playwright
            except Exception as e:
                error_msg = str(e).lower()
                if "target page, context or browser has been closed" in error_msg or "existing browser session" in error_msg or "in use" in error_msg:
                    logger.warning(f"⚠️ Profile in use or corrupt. Attempting to clean lock files (Attempt {attempt+1}/{MAX_RETRIES})")
                    _clean_grok_locks(self.profile_path)
                    await asyncio.sleep(2)
                    continue
                else:
                    await playwright.stop()
                    logger.error(f"❌ Failed to launch browser: {e}")
                    raise e
        
        # If we got here, all retries failed
        await playwright.stop()
        raise RuntimeError(f"Could not launch browser after {MAX_RETRIES} attempts.")
        
        await playwright.stop()
        raise RuntimeError(f"Failed to launch Grok browser context for profile {self.profile_path} after multiple attempts.")


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
        sound_effect: Optional[str] = None,
        emotion: str = "neutrally",
        grok_video_prompt: Optional[dict] = None,
        sfx: Optional[list[str]] = None,
        music_notes: Optional[str] = None
    ) -> Path:
        """
        Animate an image using Grok Imagine with full serialization.
        """
        # CRITICAL: Hold the lock for the ENTIRE duration of the generation.
        # This prevents concurrent Grok requests from fighting over the same profile.
        async with _grok_lock:
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
                        sound_effect=sound_effect,
                        emotion=emotion,
                        external_page=page, # Pass the active page
                        grok_video_prompt=grok_video_prompt,
                        sfx=sfx,
                        music_notes=music_notes
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


