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
        
        # Ensure it starts with the duration if not present (e.g. "10s: ")
        if not re.search(r'^[0-9]+s:', final_prompt):
             duration_prefix = "10s: " # Default to 10s for Grok Imagine
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
    
    DURATION_SELECTORS = {
        "5s": ["[data-duration='5']", "button:has-text('5s')", ".duration-5", "[data-duration='6']", "button:has-text('6s')", ".duration-6"],
        "6s": ["[data-duration='5']", "button:has-text('5s')", ".duration-5", "[data-duration='6']", "button:has-text('6s')", ".duration-6"],
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
            # Broader matches for text inside any clickable element
            "text=9:16",
            "div:text-is('9:16')",
            "span:text-is('9:16')",
        ],
        "16:9": [
            "button[aria-label='16:9']",
            "button[aria-label*='Landscape']",
            "button[aria-label*='Horizontal']",
            "[aria-label='16:9']",
            "button:has-text('16:9')",
            "button:has-text('Landscape')",
            "button:has-text('Horizontal')",
            ".aspect-landscape",
            "button:has-text('16')", # Partial match fallback
            "svg:has-text('16:9')",
            "button:has(svg[aria-label='16:9'])",
            "text=16:9",
            "div:text-is('16:9')",
            "span:text-is('16:9')",
        ],
        "1:1": [
            "button[aria-label='1:1']",
            "button[aria-label*='Square']",
            "[aria-label='1:1']",
            "button:has-text('1:1')",
            "button:has-text('Square')",
        ],
    }

    RESOLUTION_SELECTORS = {
        "720p": ["button:has-text('720p')", "[data-resolution='720']"],
        "480p": ["button:has-text('480p')", "[data-resolution='480']"],
    }
    
    @classmethod
    async def configure(cls, page: Page, duration: str = "10s", aspect: str = "9:16", resolution: str = "720p"):
        """Set duration and aspect ratio before generating."""
        logger.info(f"⚙️ Configuring video settings: duration={duration}, aspect={aspect}")
        
        # ── Step 1: Open the "Video/Image" icon popup ──
        # The user says: "set aspect ratio by clicking video/image icon to open pop"
        dropdown_opened = False
        try:
            toggle_selectors = [
                 "button:has-text('Video')",
                 "button:has-text('Image')",
                 "button[aria-label='Model select']",
                 "button[aria-label='Settings']",
                 "[data-testid='settings-button']",
            ]
            
            for selector in toggle_selectors:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    logger.info(f"📂 Clicking toggle icon to open popup: {selector}")
                    await btn.click()
                    dropdown_opened = True
                    
                    # DYNAMIC WAIT: Wait for any aspect ratio selector to become visible
                    # instead of a fixed 1.5s sleep.
                    all_aspect_selectors = [sel for sublist in cls.ASPECT_SELECTORS.values() for sel in sublist]
                    try:
                        # Wait for at least one aspect ratio button to appear (indicating popup is open)
                        # We use a combined selector for efficiency
                        combined_aspect_selector = ", ".join(all_aspect_selectors[:5]) # Focus on primary ones
                        await page.wait_for_selector(combined_aspect_selector, state="visible", timeout=3000)
                    except:
                        # Fallback to short sleep if selector wait fails
                        await asyncio.sleep(0.5)
                    break
        except Exception as e:
            logger.warning(f"Failed to open settings popup: {e}")
        
        # ── Step 2: Set Aspect Ratio inside popup ──
        aspect_clicked = False
        for selector in cls.ASPECT_SELECTORS.get(aspect, []):
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=1000)
                    logger.info(f"✅ Set aspect ratio: {aspect}")
                    aspect_clicked = True
                    break
            except: continue
        
        # ── Step 3: Set Duration ──
        duration_key = f"{duration}s" if isinstance(duration, (int, float)) else str(duration)
        if not duration_key.endswith("s"):
            duration_key += "s"
            
        duration_clicked = False
        for selector in cls.DURATION_SELECTORS.get(duration_key, []):
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=1000)
                    logger.info(f"✅ Set duration: {duration_key}")
                    duration_clicked = True
                    break
            except: continue
            
        if not duration_clicked:
            # Fallback if specific button isn't found, maybe click a raw toggle if available
            logger.warning(f"⚠️ Could not find duration button for {duration_key} inside popup.")

        # ── Step 4: Set Resolution ──
        for selector in cls.RESOLUTION_SELECTORS.get(resolution, []):
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=1000)
                    logger.info(f"✅ Set resolution: {resolution}")
                    break
            except: continue

        # ── Step 5: Close popup ──
        if dropdown_opened:
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except: pass
        
        if not aspect_clicked:
            logger.warning(f"⚠️ Could not find aspect ratio button for {aspect} inside popup.")

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
                music_notes=music_notes
            )
            # Ensure it starts with duration for the refinement pass
            if not re.search(r'^[0-9]+s:', prompt):
                 prompt = f"{duration} {prompt}"
            
            print(f"\n🚀 FINAL REFINEMENT PROMPT:\n{prompt}\n")

            # ── Step 3: Attach Image (The SEED Pass) ──
            # We follow the User's "Seed + Continue" workflow:
            # Pass 1: Image only, NO prompt.
            logger.info(f"📤 Pass 1 (SEED): Attaching image: {image_path.name}...")
            upload_success = False
            
            upload_selectors = ["button:has-text('Upload image')", "button[aria-label*='Attach']", "input[type='file']"]
            for selector in upload_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0:
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(str(image_path))
                        logger.info(f"✅ Image attached via {selector}")
                        upload_success = True
                        break
                except: continue
            
            # ── Step 3.5: Click "Make video" for the Seed ──
            # Since prompt is empty, Grok will just animate the image "sensibly"
            logger.info("🎬 Pass 1/2: Clicking 'Make video' for the initial Seed animation...")
            
            # 3.5.1: Wait for upload to complete (indicated by the appearance of the "Remove" button)
            logger.info("⏳ Waiting for image upload to finalize...")
            try:
                # Look for the close/remove button on the attached image thumbnail
                await page.wait_for_selector("button[aria-label*='Remove'], button:has(svg:has-path[d*='M6']), .absolute.top-1.right-1 button", state="visible", timeout=10000)
                logger.info("✅ Upload confirmed (Remove button detected).")
                
                # IMPORTANT: Add a short stabilization sleep after the "Remove" button appears.
                # The frontend UI and internal React/Next.js state might still be propagating changes 
                # (e.g., enabling the "Make a video" button).
                await asyncio.sleep(2)
            except:
                logger.warning("🕒 Upload confirmation (Remove button) timed out, attempting click anyway...")

            make_video_clicked = False
            make_video_selectors = [
                 # 1. Direct aria-label (Most stable if it exists)
                "button[aria-label='Make video']",
                # 2. Text match inside a button, excluding the search bar
                "button:has-text('Make video'):not([aria-label='Search'])",
                # 3. Floating action button parent (Bottom right corner of prompt area)
                ".absolute.bottom-4.right-4 button:has-text('Make video')", 
                ".absolute.bottom-3.right-3 button:has-text('Make video')",
                # 4. Role-based matching
                "div[role='button']:has-text('Make video')",
                # 5. Icon + Text wrapper
                "button:has(svg):has-text('Make video')",
                # 6. Ultra-generic fallback
                "text='Make video'"
            ]
            combined_selector = ", ".join(make_video_selectors)
            
            for attempt in range(15): 
                try:
                    # Check if button is visible and enabled
                    btn = await page.wait_for_selector(combined_selector, state="visible", timeout=3000)
                    if btn:
                        # Ensure it's not disabled
                        is_disabled = await btn.evaluate("el => el.disabled || el.getAttribute('aria-disabled') === 'true'")
                        if is_disabled:
                            logger.info(f"⏳ 'Make video' button is disabled (Attempt {attempt+1}), waiting...")
                            await asyncio.sleep(1)
                            continue

                        await btn.scroll_into_view_if_needed()
                        await btn.click(force=True, timeout=5000)
                        logger.info("✅ Successfully clicked 'Make video' via Playwright locator.")
                        make_video_clicked = True
                        break
                except:
                    # JS Fallback - very aggressive
                    clicked = await page.evaluate("""() => {
                        const findBtn = () => {
                            const candidates = Array.from(document.querySelectorAll('button, [role="button"], span, div'));
                            return candidates.find(b => 
                                b.innerText && 
                                b.innerText.toLowerCase().includes('make video') &&
                                b.getBoundingClientRect().width > 0
                            );
                        };
                        const b = findBtn();
                        if (b && !b.disabled && b.getAttribute('aria-disabled') !== 'true') {
                            b.scrollIntoView();
                            b.click(); return true;
                        }
                        return false;
                    }""")
                    if clicked:
                        logger.info("✅ Successfully clicked 'Make video' via JS fallback.")
                        make_video_clicked = True
                        break
                await asyncio.sleep(1)

            # ── Step 4: Multi-Pass Polling (Seed -> Extend -> Refine -> Download) ──
            logger.info("⏳ Starting Multi-Pass Polling (Seed + Refine)...")
            
            output_dir = Path(os.getcwd()) / "generated_videos"
            output_dir.mkdir(exist_ok=True)
            output = output_dir / f"clip_{uuid4()}.mp4"
            
            # Multi-Pass State Management
            current_pass = "SEED" 
            is_extended = False
            is_refined = False
            last_video_src = None # Track URL to detect NEW generation

            max_wait = 400 # Increased for dual-pass
            poll_interval = 4
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < max_wait:
                if page.is_closed(): break
                elapsed = int(asyncio.get_event_loop().time() - start_time)

                # 1. Check for standard generation indicators
                is_generating = False
                gen_selectors = [
                    "text='Generating...'", "text='Thinking...'", "text='Generative...'",
                    "text='Finalizing...'", ".animate-pulse", "button:has-text('Cancel Video')",
                    "div[role='progressbar']", "svg.animate-spin"
                ]
                for ind in gen_selectors:
                    try:
                        if await page.locator(ind).first.is_visible():
                            is_generating = True
                            if elapsed % 20 == 0: logger.info(f"⏳ Grok is busy ({current_pass} pass)...")
                            break
                    except: continue

                # 2. Check for dual-video scenario ("I prefer this" buttons)
                try:
                    prefer_buttons = page.locator("button:has-text('I prefer this'), button:has-text('prefer this')")
                    prefer_count = await prefer_buttons.count()
                    if prefer_count > 0:
                        logger.info(f"🎭 Grok generated {prefer_count} video options! Clicking 'I prefer this' on the first one...")
                        await prefer_buttons.first.click()
                        await asyncio.sleep(3) # Wait for UI to settle after selection
                        logger.info("✅ Selected preferred video. Resuming flow...")
                        continue # Re-enter loop to pick up the selected video
                except: pass

                # 3. Check if video is "Ready" enough to continue/download
                video_ready = await page.evaluate("""
                    () => {
                        const v = document.querySelector('video');
                        if (!v) return { ready: false };
                        return { ready: v.readyState >= 3, duration: v.duration, src: v.src };
                    }
                """)
                
                # A video is "Truly New" if its SRC is different from the last pass
                is_new_video = video_ready.get("src") != last_video_src
                ready = video_ready.get("ready") and video_ready.get("duration", 0) > 0 and not is_generating and is_new_video

                if ready:
                    # --- BRANCH A: Handle Initial Seed Complete ---
                    if current_pass == "SEED":
                        last_video_src = video_ready.get("src")
                        logger.info(f"🌱 Seed Pass Complete (src={last_video_src[:40]}...).")
                        
                        # MANDATORY: Give Grok UI 5 seconds to show buttons (Continue/Extend)
                        await asyncio.sleep(5)
                        
                        if needs_extend and not is_extended:
                            logger.info("🔄 Needs Extend: Clicking 'Extend video' for duration...")
                            extend_clicked = False
                            # Strictly look for 'Extend' for duration
                            for sel in ["button:has-text('Extend video')", "button:has-text('Extend')", "[aria-label*='Extend']"]:
                                try:
                                    btn = page.locator(sel).first
                                    if await btn.count() > 0:
                                        await btn.click(); extend_clicked = True; break
                                except: continue
                            
                            if extend_clicked:
                                await asyncio.sleep(3)
                                ext_dur = extend_duration or "6s"
                                await VideoSettings.configure(page, duration=ext_dur, aspect=aspect)
                                await asyncio.sleep(1)
                                try: await page.keyboard.press("Enter")
                                except: pass
                                
                                logger.info(f"🎬 Extension ({ext_dur}) started. Waiting for EXTENDED clip...")
                                current_pass = "EXTENDING"
                                start_time = asyncio.get_event_loop().time()
                                await asyncio.sleep(5) 
                                continue
                        
                        # Move directly to Refinement if no extension
                        current_pass = "REFINING"
                        is_extended = True
                        # Don't 'continue' here, fall through to click REFINEMENT immediately
                    
                    # --- BRANCH B: Handle Extension Complete ---
                    if current_pass == "EXTENDING":
                        last_video_src = video_ready.get("src")
                        logger.info(f"✅ Extension Complete (src={last_video_src[:40]}...). Moving to Refinement...")
                        current_pass = "REFINING"
                        is_extended = True
                        # Fall through to click REFINEMENT

                    # --- BRANCH C: Trigger Refinement (Manual Continue) ---
                    if current_pass == "REFINING" and not is_refined:
                        logger.info("🎭 PASS 2/2: Refining Scene — Typing 'Continue this frame' into Input...")
                        
                        try:
                            # 1. Type the Refinement Prompt into the main input box
                            prompt_input = page.locator(".ProseMirror, textarea, [contenteditable='true']").first
                            await prompt_input.click()
                            
                            # Prefix with "Continue this frame" as per user request
                            refine_text = f"Continue this frame. {prompt}"
                            await prompt_input.fill(refine_text)
                            await asyncio.sleep(1)
                            
                            # 2. Click the 'Submit' (Up Arrow) button
                            submit_clicked = False
                            submit_selectors = [
                                "button[aria-label='Submit']",
                                "button:has(svg.fa-arrow-up)", 
                                "button:has(svg):has-text('')", # Often an icon-only button
                                ".absolute.bottom-2.right-2 button", # Position-based fallback
                                "button.rounded-full:has(svg)" # Circular icon button
                            ]
                            
                            for sel in submit_selectors:
                                try:
                                    btn = page.locator(sel).last # Usually the rightmost/last button
                                    if await btn.count() > 0 and await btn.is_visible():
                                        await btn.click(force=True)
                                        submit_clicked = True
                                        break
                                except: continue
                                
                            if not submit_clicked:
                                # Final Keyboard Fallback
                                await page.keyboard.press("Enter")
                                submit_clicked = True
                            
                            logger.info("💎 Refinement Pass submitted. Waiting for FINAL high-quality clip...")
                            current_pass = "DOWNLOADING" 
                            is_refined = True
                            start_time = asyncio.get_event_loop().time() 
                            last_video_src = video_ready.get("src") # Capture to wait for CHANGE
                            await asyncio.sleep(10) 
                            continue
                            
                        except Exception as e:
                            logger.error(f"❌ Refinement injection failed: {e}")
                            logger.warning("⚠️ Falling back to current Seed/Extended clip.")
                            current_pass = "DOWNLOADING"

                    # --- BRANCH D: Final Download ---
                    if current_pass == "DOWNLOADING":
                        logger.info("🎯 Final Refined Clip is ready! Starting download...")
                        
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

                await asyncio.sleep(poll_interval)

            raise RuntimeError(f"Grok Multi-Pass generation failed or timed out after {max_wait}s")

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
            # Handle both int and string durations
            duration_str = str(duration) if isinstance(duration, str) and duration.endswith('s') else f"{duration}s"
            
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

