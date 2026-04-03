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
        music_notes: Optional[str] = None,
        duration: Optional[str] = None
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
        if grok_video_prompt and grok_video_prompt.get("image_to_video_prompt"):
            base_prompt = grok_video_prompt["image_to_video_prompt"]
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
            
            # FORCE REMOVE SUBTITLES: Explicit instruction
            prompt_parts.append("Clean video, no text overlay, no subtitles")
            
            base_prompt = ". ".join(prompt_parts)

        # Apply global negative prompt for text/subtitles if not already present
        negative_text_prompt = "Clean video, no text overlay, no subtitles"
        if negative_text_prompt not in base_prompt:
             base_prompt = f"{base_prompt}. {negative_text_prompt}"

        # Apply timeline formatting to the base prompt
        base_prompt = format_timeline(base_prompt)
        
        # NOTE: AUDIO and SFX blocks removed — Grok Imagine ignores dialogue/SFX.
        # Dialogue is now routed to Edge-TTS narration in the stitch pipeline.
        # Keeping parameters in function signature for backward compatibility.

        # Final assembly — motion-only prompt for Grok
        final_prompt = base_prompt.strip()
        
        # --- Strictly Enforce Duration Prefix ---
        # Remove any existing duration prefix (e.g. "10s: " or "6s: ")
        import re
        final_prompt = re.sub(r'^[0-9]+s:?\s*', '', final_prompt)
        
        # --- Strip Aspect Ratio Keywords ---
        # Grok sometimes literalizes '16:9' or 'Landscape' if it's in the prompt text.
        # Since we set these via the UI buttons, we should strip them from the prompt string.
        ar_keywords = [
            r'16:9', r'9:16', r'1:1', r'21:9', r'4:3', r'3:2', r'2:3',
            r'landscape', r'portrait', r'widescreen', r'cinematic wide', r'vertical video', r'shorts'
        ]
        for kw in ar_keywords:
            # Match word boundaries or start/end of string to be safe
            final_prompt = re.sub(rf'(?i)(?:\s*,?\s*|\s*-\s*|\s*\|\s*){kw}(?:\s*,?\s*|\s*-\s*|\s*\|\s*)', ', ', final_prompt)
            # Second pass for remaining standalone instances
            final_prompt = re.sub(rf'(?i)\b{kw}\b', '', final_prompt)

        # Cleanup whitespace and commas
        final_prompt = re.sub(r',\s*,', ',', final_prompt)
        final_prompt = re.sub(r'^\s*,\s*|\s*,\s*$', '', final_prompt)
        final_prompt = re.sub(r'\s+', ' ', final_prompt).strip()

        # Add the target duration
        duration_val = str(duration or "10s")
        if not duration_val.endswith("s"): duration_val += "s"
        
        # Ensure it's exactly one of "6s" or "10s" (Grok's supported values)
        if duration_val not in ["6s", "10s"]:
            logger.warning(f"⚠️ PromptBuilder: Unsupported duration {duration_val}, defaulting to 10s prefix.")
            duration_val = "10s"
            
        final_prompt = f"{duration_val}: {final_prompt}"

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
                if current_url != original_url and any(x in current_url for x in ["/post/", "/status/", "/project/"]):
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
    
    # NOTE: Selectors now use :text-is() for EXACT matching (not substring)
    DURATION_SELECTORS = {
        "6s": ["button:text-is('6s')", "button:has-text('6s')", "[data-duration='6']", "button:text-is('5s')", "[data-duration='5']"],
        "5s": ["button:text-is('5s')", "[data-duration='5']", "button:text-is('6s')", "[data-duration='6']"],
        "10s": ["button:text-is('10s')", "button:has-text('10s')", "[data-duration='10']"],
    }
    
    # These are highly robust locators based on the DOM structure provided by the user.
    ASPECT_SELECTORS = {
        "16:9": ["button[role='option']:has-text('16:9')", "[role='menuitem']:has-text('16:9')"],
        "9:16": ["button[role='option']:has-text('9:16')", "[role='menuitem']:has-text('9:16')"],
        "1:1":  ["button[role='option']:has-text('1:1')",  "[role='menuitem']:has-text('1:1')"]
    }
    
    # We will favor custom JS exact-text matching for speed and reliability,
    # but keep these for generic references.
    DURATION_SELECTORS  = { "6s": [""], "10s": [""] }
    RESOLUTION_SELECTORS= { "480p": [""], "720p": [""] }

    @staticmethod
    async def configure(page: Page, duration: str = "10s", aspect: str = "9:16", resolution: str = "720p"):
        """Sets the video generation parameters in the Grok UI row using robust fuzzy locators."""
        logger.info(f"⚙️ VideoSettings.configure: duration={duration}, aspect={aspect}, resolution={resolution}")
        
        # ── Step 0: Ensure "Video" mode is active ──
        try:
            # Click elements that exactly match "Video"
            await page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('button, div, span'));
                const videoBtn = els.find(el => {
                    if (el.offsetWidth === 0 || el.offsetHeight === 0) return false;
                    const text = (el.innerText || "").trim();
                    return text === "Video";
                });
                if (videoBtn) videoBtn.click();
            }""")
            await asyncio.sleep(0.5)
        except: pass

        duration_key = str(duration)
        if not duration_key.endswith("s"): duration_key += "s"

        # ── Step 1: Duration & Resolution via Playwright Locators ──
        async def robust_click(target: str, setting_name: str) -> bool:
            # wait for target text to appear somewhere in a clickable element
            try:
                await page.wait_for_selector(f"text='{target}'", state="visible", timeout=3000)
            except: pass

            # Priority: find visible buttons/divs
            selectors = [
                f"button:visible:has-text('{target}')",
                f"div[role='button']:visible:has-text('{target}')",
                f"text='{target}'"
            ]
            for sel in selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0:
                        await btn.scroll_into_view_if_needed()
                        await btn.click(force=True, timeout=2000)
                        logger.info(f"✅ Set {setting_name}: {target}")
                        return True
                except: continue
                
            # JS Fallback if Playwright fails
            clicked = await page.evaluate(f"""(target) => {{
                const targetLower = target.toLowerCase();
                const els = Array.from(document.querySelectorAll('button, div, span'));
                const el = els.find(el => {{
                    if (el.offsetWidth === 0 || el.offsetHeight === 0) return false;
                    return (el.innerText || "").trim().toLowerCase() === targetLower;
                }});
                if (el) {{
                    ['mousedown', 'mouseup', 'click'].forEach(t => el.dispatchEvent(new MouseEvent(t, {{ bubbles: true }})));
                    return true;
                }}
                return false;
            }}""", target)
            if clicked: logger.info(f"✅ Set {setting_name}: {target} (via JS)")
            return clicked

        # Select Duration and Resolution
        dur_ok = await robust_click(duration_key, "Duration")
        res_ok = await robust_click(resolution, "Resolution")

        # ── Step 2: Handle Aspect Ratio (Dropdown) ──
        aspect_ok = False
        
        # Using the exact DOM structure provided by the user:
        # Trigger: button[aria-label="Aspect Ratio"]
        # Menu Items: [role="menuitem"] containing span with text (e.g., "9:16")
        
        for i in range(3):
            try:
                # 1. Look for the trigger button
                trigger = page.get_by_role("button", name="Aspect Ratio")
                if await trigger.count() == 0:
                    # Fallback to finding by any button that looks like a ratio
                    trigger = page.locator("button:visible").filter(has_text=":").first
                
                if await trigger.count() > 0:
                    # Check if already open
                    is_open = await trigger.get_attribute("data-state") == "open"
                    if not is_open:
                        logger.info("🖱️ Opening Aspect Ratio dropdown...")
                        await trigger.click(force=True)
                        await asyncio.sleep(0.5)
                    
                    # 2. Find the menu item
                    # The user's DOM shows role="menuitem" with a span child
                    item = page.get_by_role("menuitem").filter(has_text=aspect)
                    if await item.count() > 0:
                        await item.first.click(force=True)
                        logger.info(f"✅ Set Aspect Ratio: {aspect}")
                        aspect_ok = True
                        break
                    else:
                        # Fallback for hidden menu items or different roles
                        item_clicked = await page.evaluate(f"""(ratio) => {{
                            const els = Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], button, span'));
                            const target = els.find(el => {{
                                if (el.offsetWidth === 0 || el.offsetHeight === 0) return false;
                                return (el.innerText || "").trim() === ratio;
                            }});
                            if (target) {{ target.click(); return true; }}
                            return false;
                        }}""", aspect)
                        if item_clicked:
                            logger.info(f"✅ Set Aspect Ratio: {aspect} (fallback)")
                            aspect_ok = True
                            break
            except Exception as e:
                logger.debug(f"Aspect ratio attempt {i} failed: {e}")
            await asyncio.sleep(0.5)

        if not aspect_ok:
            logger.warning(f"⚠️ FAILED to set aspect ratio to {aspect}!")

        # ── Step 3: Close any open popups (like the aspect ratio menu if it didn't auto-close) ──
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except: pass
        
        if not dur_ok:
            logger.warning(f"⚠️ FAILED to set duration to {duration_key}!")
        if not aspect_ok:
            logger.warning(f"⚠️ FAILED to set aspect ratio to {aspect}!")
        if not res_ok:
            logger.info(f"ℹ️ FAILED to set resolution {resolution} (might not be available).")

    @staticmethod
    def verify_clip_duration(clip_path: Path, expected_duration: float) -> bool:
        """Use ffprobe to verify actual clip duration matches expected."""
        try:
            import ffmpeg
            probe = ffmpeg.probe(str(clip_path))
            actual = float(probe['streams'][0]['duration'])
            tolerance = 1.5  # 1.5s tolerance because AI generators are imprecise
            
            if abs(actual - expected_duration) > tolerance:
                logger.warning(f"⚠️ Duration mismatch: expected {expected_duration}s, got {actual}s")
                return False
            return True
        except Exception as e:
            logger.error(f"❌ Failed to verify duration via ffprobe: {e}")
            return False  # Stricter: return False if we can't be sure it's valid


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
            ctx = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_PATH),
                headless=False,
                accept_downloads=True,
                ignore_default_args=["--enable-automation"],
                args=args,
                viewport={'width': 1100, 'height': 800}
            )
            # Register with global shutdown registry
            try:
                from apps.api.main import _active_browsers
                _active_browsers.append((ctx, playwright))
            except ImportError:
                pass
            return ctx
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
    resolution: str = "720p",
    external_page: Optional[Page] = None,
    grok_video_prompt: Optional[dict] = None,
    sfx: Optional[list[str]] = None,
    music_notes: Optional[str] = None,
    dialogue_mode: bool = False,
    needs_extend: bool = False,
    extend_duration: Optional[str] = None
) -> Path:
    logger.info(f"🎬 generate_single_clip: Starting for duration={duration}, aspect={aspect}, resolution={resolution}")
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
            # OPTIMIZATION: Only navigate if we aren't already on the imagine page
            if "grok.com/imagine" not in page.url:
                logger.info("🌐 Navigating to Grok Imagine...")
                await page.goto("https://grok.com/imagine", wait_until="domcontentloaded", timeout=60000)
            else:
                logger.info("🚀 Already on Grok Imagine, skipping navigation.")
            
            # DYNAMIC WAIT: Wait for the prompt area instead of fixed sleep
            try:
                # Use a combined selector for all possible prompt areas
                await page.wait_for_selector(".ProseMirror, textarea, [contenteditable='true']", state="visible", timeout=5000)
            except:
                logger.warning("Timeout waiting for prompt area, continuing anyway...")
            
            # MANDATORY: Close the Upload dialog that auto-opens on Grok Imagine
            try:
                # The upload dialog contains "Upload File" / "Drop your media" text
                # and has a close (×) button. Try multiple strategies to dismiss it.
                upload_dialog_selectors = [
                    "button:has-text('Upload File')",
                    "text='Drop your media here'",
                    "text='Upload'",
                ]
                dialog_detected = False
                for sel in upload_dialog_selectors:
                    try:
                        if await page.locator(sel).first.is_visible(timeout=2000):
                            dialog_detected = True
                            break
                    except:
                        continue

                if dialog_detected:
                    logger.info("🧹 Upload dialog detected, closing it...")
                    closed = False

                    # Strategy 1: Click the × (close) button on the dialog
                    close_btn_selectors = [
                        "button[aria-label='Close']",
                        "button[aria-label='close']",
                        "button[aria-label='Dismiss']",
                        # Generic close buttons near dialog headers (× icon)
                        "div[role='dialog'] button:has(svg)",
                        "[data-state='open'] button:has(svg)",
                    ]
                    for close_sel in close_btn_selectors:
                        try:
                            close_btn = page.locator(close_sel).first
                            if await close_btn.count() > 0 and await close_btn.is_visible(timeout=1000):
                                await close_btn.click(timeout=2000)
                                logger.info(f"✅ Closed upload dialog via {close_sel}")
                                closed = True
                                break
                        except:
                            continue

                    # Strategy 2: Press Escape to dismiss overlays
                    if not closed:
                        await page.keyboard.press("Escape")
                        logger.info("✅ Pressed Escape to close upload dialog.")
                        closed = True

                    await asyncio.sleep(0.5)

                    # Strategy 3: Click outside the dialog to dismiss it (click on backdrop)
                    if not closed:
                        try:
                            await page.mouse.click(10, 10)
                            logger.info("✅ Clicked outside dialog to close it.")
                        except:
                            pass
                        await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Upload dialog check: {e}")

            # Also close any other leftover popups from previous runs/failed settings
            try:
                if await page.locator("div[role='menu'], .absolute.z-50").count() > 0:
                    logger.info("🧹 Clearing leftover overlays before starting...")
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
            except: pass

            if await check_rate_limit(page):
                raise RateLimitError("Rate limit detected")

            # ... (Step 1-3 logic remains same)
            # ── Step 1: Set Aspect Ratio (via pop-up) ──
            await VideoSettings.configure(page, duration=duration, aspect=aspect, resolution=resolution)

            # ── Step 2: Build Prompt (but don't paste yet) ──
            prompt = PromptBuilder.build(
                character_pose, camera_angle, style_suffix,
                motion_description, dialogue,
                character_name=character_name, emotion=emotion, sound_effect=sound_effect,
                grok_video_prompt=grok_video_prompt,
                sfx=sfx,
                music_notes=music_notes,
                duration=duration
            )
            # Strictly enforce the correct duration prefix (e.g. "6s: ")
            # We override any default that PromptBuilder might have added if it's wrong
            duration_val = duration.replace("s", "")
            target_prefix = f"{duration_val}s: "
            
            if not prompt.startswith(target_prefix):
                # Remove any existing duration prefix ([0-9]+s:)
                prompt = re.sub(r'^[0-9]+s:?\s*', '', prompt)
                prompt = target_prefix + prompt
            
            # ── Step 3: Attach Image (The SEED Pass) ──
            # We follow the User's "Seed + Continue" workflow:
            upload_success = False
            # Step 3a: Force-Upload via hidden input[type='file'] (Safest bypass of UI)
            try:
                # Grok hides its file input or disables it until a UI state change occurs. 
                # This explicitly forces it alive.
                await page.evaluate("""() => {
                    let inp = document.querySelector('input[type="file"]');
                    if (!inp) {
                        inp = document.createElement('input');
                        inp.type = 'file';
                        inp.id = 'fake-grok-upload';
                        document.body.appendChild(inp);
                    }
                    inp.style.display = 'block';
                    inp.style.opacity = '1';
                    inp.style.visibility = 'visible';
                    inp.style.width = '100px';
                    inp.style.height = '100px';
                    inp.removeAttribute('disabled');
                    inp.removeAttribute('aria-hidden');
                }""")
                await asyncio.sleep(0.5)
                
                # Use our fake or real input to trigger set_files
                await page.locator("input[type='file']").first.set_input_files(str(image_path), timeout=3000)
                logger.info("✅ Image attached via direct force input[type='file']")
                
                # Cleanup: Hide it again
                await page.evaluate("""() => {
                    const inp = document.querySelector('input[type="file"]');
                    if (inp) {
                        inp.style.display = 'none';
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""")
                upload_success = True
            except Exception as e:
                logger.warning(f"⚠️ Direct input upload failed: {e}")
                
            # Step 3b: If direct input fails, use the robust Option 3 Visual UI method
            if not upload_success:
                try:
                    # 1. Click the + button FIRST to open the popup menu
                    plus_btn_clicked = await page.evaluate("""() => {
                        const els = Array.from(document.querySelectorAll('button, div'));
                        const btn = els.find(el => {
                            if (el.offsetWidth === 0 || el.offsetHeight === 0) return false;
                            const text = (el.innerText || "").trim();
                            const aria = (el.getAttribute('aria-label') || "").toLowerCase();
                            // Look for the '+' icon button
                            return text === "+" || aria.includes('attach') || (text === "" && el.querySelector('svg'));
                        });
                        if (btn) { btn.click(); return true; }
                        return false;
                    }""")
                    
                    await asyncio.sleep(1)
                    
                    # 2. Now wait for the file chooser triggered by "Upload"
                    async with page.expect_file_chooser(timeout=8000) as fc_info:
                        await page.evaluate("""() => {
                            const els = Array.from(document.querySelectorAll('button, div, [role="menuitem"]'));
                            const uploadBox = els.find(el => {
                                if (el.offsetWidth === 0 || el.offsetHeight === 0) return false;
                                const text = (el.innerText || "").toLowerCase();
                                return text.includes("upload") || text.includes("image");
                            });
                            if (uploadBox) uploadBox.click();
                        }""")
                    
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(image_path))
                    logger.info("✅ Image attached via Visual + PopUp Menu")
                    upload_success = True
                    
                except Exception as e:
                    logger.warning(f"⚠️ UI-driven upload sequence failed entirely: {e}")
            
            # ── Step 3.5: Click "Make video" for the Seed ──
            # GROK UI FIX: The arrow button is DISABLED if the prompt is empty.
            # We MUST type a tiny character (like '.') to enable it, THEN start.
            try:
                # 3.5.1: Stabilize UI
                await asyncio.sleep(2)
                prompt_input = page.locator(".ProseMirror, textarea, [contenteditable='true']").first
                await prompt_input.click()
                await prompt_input.fill("") # Clear any junk
                await page.keyboard.type(".")
                logger.info("⌨️ Typed '.' to enable the 'Make video' button for the seed.")
            except: pass

            async def robust_make_video_click(page_obj, attempt_num):
                # Aggressive locator: look for the black circle button with up arrow
                submit_selectors = [
                    "button.bg-neutral-900.rounded-full",
                    "button[aria-label='Submit']",
                    "button[data-testid='send-chat-message-button']",
                    "button:has(svg:has(path[d*='M6']))",
                    "button:right-of('.ProseMirror')"
                ]
                for sel in submit_selectors:
                    try:
                        btn = page_obj.locator(sel).last
                        if await btn.count() > 0 and await btn.is_visible(timeout=500):
                            await btn.scroll_into_view_if_needed()
                            await btn.click(force=True, timeout=2000)
                            return True
                    except: continue
                # Coordinate Fallback relative to prompt container
                try:
                    pm = page_obj.locator(".ProseMirror, textarea").first
                    box = await pm.bounding_box()
                    if box:
                        # Click near the bottom right of the prompt box where the button is
                        await page_obj.mouse.click(box['x'] + box['width'] - 20, box['y'] + box['height'] - 20)
                        return True
                except: pass
                return False

            logger.info("🎬 Pass 1/2: Clicking 'Make video' for the initial Seed animation...")
            make_video_clicked = False
            for attempt in range(15): 
                if await robust_make_video_click(page, attempt):
                    logger.info("✅ Successfully clicked 'Make video' for seed.")
                    make_video_clicked = True
                    break
                await asyncio.sleep(1)
            
            if not make_video_clicked:
                logger.error("❌ Failed to click 'Make video' for seed after all attempts.")

            # ── NEW WORKFLOW: Cancel-Trick Injection ──
            logger.info("⚡ Executing Cancel-Trick: Cancelling initial seed to attach image context...")
            
            # Wait for text "Generating" or the Cancel button
            for i in range(20):
                try:
                    if await page.locator("button:has-text('Cancel Video'), text='Generating', .animate-pulse").first.is_visible(timeout=500):
                        break
                except: pass
                await asyncio.sleep(0.5)

            # Click the Cancel Video button with ultra-robust strategy (Native + Coordinates + JS)
            cancel_clicked = False
            for attempt in range(25):
                try:
                    # 1. Primary: Text locator filtered for visibility
                    btn = page.locator("text='Cancel Video'").last
                    if await btn.count() > 0 and await btn.is_visible(timeout=500):
                        await btn.scroll_into_view_if_needed()
                        await btn.hover() # Trigger any hover states
                        await btn.click(force=True, timeout=2000)
                        cancel_clicked = True
                        break
                    
                    # 2. Secondary: Find coordinates via JS for precise mouse action
                    coords = await page.evaluate("""() => {
                        const els = Array.from(document.querySelectorAll('*'));
                        const target = els.find(el => {
                            if (el.offsetWidth === 0 || el.offsetHeight === 0) return false;
                            const text = (el.innerText || "").toLowerCase();
                            return text.includes("cancel video") || text.includes("cancel");
                        });
                        if (target) {
                            const rect = target.getBoundingClientRect();
                            return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, found: true };
                        }
                        return { found: false };
                    }""")
                    
                    if coords and coords['found']:
                        logger.info(f"🖱️ Found Cancel button at ({coords['x']}, {coords['y']}). Force clicking via Mouse...")
                        await page.mouse.move(coords['x'], coords['y'])
                        await page.mouse.down()
                        await page.mouse.up()
                        cancel_clicked = True
                        break
                except: pass
                await asyncio.sleep(0.3)
            
            if cancel_clicked:
                logger.info("✅ Cancel button clicked. ⏳ Waiting for generation overlay to disappear...")
                # Synchronization: Wait until the button is GONE to avoid double-gen
                for i in range(30):
                    try:
                        still_there = await page.evaluate("""() => {
                            const text = document.body.innerText.toLowerCase();
                            // Check for the "Generating" pill or "Cancel" text
                            return text.includes("cancel video") || text.includes("generating");
                        }""")
                        if not still_there:
                            logger.info("✅ Generation overlay is gone.")
                            break
                        # Also check if it's already flipped to a video element
                        if await page.locator("video").first.is_visible(timeout=100):
                            break
                    except: break
                    await asyncio.sleep(0.3)
            else:
                logger.warning("⚠️ Could not find Cancel button. Proceeding to inject prompt anyway...")
                
            await asyncio.sleep(1)
            
            # ── Paste Final Prompt ──
            logger.info(f"⌨️ Injecting full prompt: {prompt[:50]}...")
            try:
                prompt_area = page.locator(".ProseMirror, textarea, [contenteditable='true']").first
                await prompt_area.click()
                await prompt_area.fill("")
                # Use evaluate to force clear just in case
                await page.evaluate("() => { const el = document.querySelector('.ProseMirror'); if(el) el.innerHTML = '<p></p>'; }")
                await prompt_area.fill(prompt)
            except:
                await page.evaluate(f"((p)=>{{ const el=document.querySelector('.ProseMirror, textarea'); if(el) el.innerText=p; }})('{prompt}')")
            
            await asyncio.sleep(1)
            
            # ── Click Make Video Again ──
            logger.info("🎬 Clicking 'Make video' for Final Generation...")
            final_clicked = False
            for attempt in range(10):
                if await robust_make_video_click(page, attempt):
                    logger.info("✅ Successfully clicked 'Make video' for Final Generation.")
                    final_clicked = True
                    break
                await asyncio.sleep(1)
                
            if not final_clicked:
                logger.error("❌ Failed to trigger Final Generation!")
                
            # ── Step 4: Simple Polling until Download Ready ──
            logger.info("⏳ Waiting for Final Generation to complete...")
            output_dir = Path(os.getcwd()) / "generated_videos"
            output_dir.mkdir(exist_ok=True)
            output = output_dir / f"clip_{uuid4()}.mp4"
            
            max_wait = 400
            poll_interval = 4
            start_time = asyncio.get_event_loop().time()
            is_generating_last_check = True

            while (asyncio.get_event_loop().time() - start_time) < max_wait:
                if page.is_closed(): break
                elapsed = int(asyncio.get_event_loop().time() - start_time)

                # Check if generating
                is_generating = False
                for ind in ["text='Generating...'", "text='Thinking...'", "text='Generative...'", "text='Finalizing...'", ".animate-pulse", "button:has-text('Cancel Video')", "div[role='progressbar']", "svg.animate-spin"]:
                    try:
                        if await page.locator(ind).first.is_visible():
                            is_generating = True
                            if elapsed % 20 == 0: logger.info("⏳ Grok is busy generating...")
                            break
                    except: continue

                # Look for "I prefer this" dual-video branch
                try:
                    prefer_buttons = page.locator("button:has-text('I prefer this'), button:has-text('prefer this')")
                    if await prefer_buttons.count() > 0:
                        logger.info("🎭 Grok generated 2 options! Clicking 'I prefer this' on the first one...")
                        await prefer_buttons.first.click()
                        await asyncio.sleep(3)
                        continue
                except: pass

                # Check video tags
                video_ready = await page.evaluate("""() => {
                    const v = document.querySelector('video');
                    if (!v) return { ready: false };
                    return { ready: v.readyState >= 3, duration: v.duration, src: v.src };
                }""")
                
                ready = video_ready.get("ready") and video_ready.get("duration", 0) > 0 and not is_generating
                
                if ready:
                    logger.info("🎯 Final Video is ready! Starting download...")
                    for sel in ["button[aria-label='Download']", "button:has-text('Download')", "[data-testid='download-button']"]:
                        try:
                            btn = page.locator(sel).first
                            if await btn.count() > 0:
                                async with page.expect_download(timeout=30000) as dl_info:
                                    await btn.click()
                                download = await dl_info.value
                                await download.save_as(output)
                                
                                if output.exists() and output.stat().st_size > 150000:
                                    logger.info(f"✅ Final Video generated and downloaded! ({output.stat().st_size} bytes)")
                                    return output
                        except: continue
                    
                    # Fallback download logic if button missing
                    src = video_ready.get("src")
                    if src and src.startswith("blob:"):
                        logger.info("📥 Downloading via blob extraction...")
                        # ... blob extraction could go here, for now rely on UI
                        pass

                await asyncio.sleep(poll_interval)

            raise RuntimeError(f"Grok single-pass generation failed or timed out after {max_wait}s")

        finally:
            # ONLY CLOSE IF WE OPENED IT
            if not external_page and browser:
                try:
                    await browser.close()
                    await pw.stop()
                    logger.info("🛑 Grok cleanup complete.")
                except: pass


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
                
                # Register with global shutdown registry
                try:
                    from apps.api.main import _active_browsers
                    _active_browsers.append((browser, playwright))
                    logger.info("📋 Grok browser registered for shutdown cleanup.")
                except ImportError:
                    pass
                    
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
            duration=6
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
        duration: int | str = 10,
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
        camera_angle: str = "Medium shot",
        dialogue: Optional[str] = None,
        sound_effect: Optional[str] = None,
        emotion: str = "neutrally",
        grok_video_prompt: Optional[dict] = None,
        sfx: Optional[list[str]] = None,
        music_notes: Optional[str] = None,
        dialogue_mode: bool = False,
        needs_extend: bool = False,
        extend_duration: Optional[str] = None
    ) -> Path:
        """
        Animate an image using Grok Imagine with full serialization.
        """
        # CRITICAL: Hold the lock for the ENTIRE duration of the generation.
        # This prevents concurrent Grok requests from fighting over the same profile.
        async with _grok_lock:
            # Handle both int and string durations with strict '6s'/'10s' mapping
            d_val = str(duration).lower().strip()
            if '6' in d_val:
                duration_str = "6s"
            elif '10' in d_val:
                duration_str = "10s"
            else:
                logger.warning(f"⚠️ GrokAnimator: Ambiguous duration '{duration}', defaulting to '10s'")
                duration_str = "10s"
            
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
                        resolution=resolution,
                        dialogue=dialogue,
                        sound_effect=sound_effect,
                        emotion=emotion,
                        external_page=page, # Pass the active page
                        grok_video_prompt=grok_video_prompt,
                        sfx=sfx,
                        music_notes=music_notes,
                        dialogue_mode=dialogue_mode,
                        needs_extend=needs_extend,
                        extend_duration=extend_duration
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
                    try:
                        # Unregister from global shutdown registry
                        try:
                            from apps.api.main import _active_browsers
                            _active_browsers[:] = [(b, p) for b, p in _active_browsers if b is not browser]
                        except ImportError:
                            pass
                        await browser.close()
                        await pw.stop()
                    except: pass
    
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
                    duration=scene.get('duration', 6)
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
            duration=6
        )
        print(f"✅ Generated: {result}")
    
    # Check for --setup flag
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        asyncio.run(setup_profile())
    else:
        asyncio.run(test_generation())

