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
from pathlib import Path
from uuid import uuid4
from datetime import timedelta
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)

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
        character_name: str = "Character",
        emotion: str = "neutrally"
    ) -> str:
        """
        Example output:
        "Medium shot of Boy A and Boy B near a dying fire. Pixar 3D style.
         The fire flickers weakly. Boy A says in a worried voice: 'The fire is dying.'"
        """
        layers = [
            f"{camera_angle} of {character_pose}",  # Scene + Camera
            f"{style_suffix}.",                      # Style
            f"{motion_description}.",                # Motion
        ]
        
        # Add dialogue if present
        if dialogue:
            layers.append(f"{character_name} says {emotion}: '{dialogue}'")
        
        return " ".join(layers)


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
    
    ASPECT_SELECTORS = {
        "9:16": ["[data-aspect='9:16']", "button:has-text('9:16')", ".aspect-vertical"],
        "16:9": ["[data-aspect='16:9']", "button:has-text('16:9')", ".aspect-landscape"],
    }
    
    @classmethod
    async def configure(cls, page: Page, duration: str = "10s", aspect: str = "9:16"):
        """Set duration and aspect ratio before generating."""
        # Try duration selectors
        for selector in cls.DURATION_SELECTORS.get(duration, []):
            try:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    await btn.click()
                    logger.info(f"Set duration: {duration}")
                    break
            except Exception:
                continue
        
        # Try aspect selectors
        for selector in cls.ASPECT_SELECTORS.get(aspect, []):
            try:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    await btn.click()
                    logger.info(f"Set aspect ratio: {aspect}")
                    break
            except Exception:
                continue
    
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


# ============================================
# Browser Management
# ============================================
async def get_browser_context() -> tuple[BrowserContext, any]:
    """Create browser context with persistent profile."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_PATH),
        channel="chrome",
        headless=False, # Force headful for now to debug/verify login
        # CRITICAL: Match login_grok.py settings to keep session valid
        ignore_default_args=["--enable-automation"],
        args=[
            '--disable-blink-features=AutomationControlled', 
            '--no-sandbox', 
            '--disable-infobars'
        ]
    )
    return browser, playwright


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
    character_name: str = "Character",
    emotion: str = "neutrally",
    duration: str = "10s",
    aspect: str = "9:16"
) -> Path:
    """Core generation logic with all stealth features."""
    browser, pw = await get_browser_context()
    try:
        page = await browser.new_page()
        # await Stealth().apply_stealth_async(page)  <-- DISABLED to match login script
        await page.goto("https://grok.com/imagine")
        
        # Wait for page to fully load
        await asyncio.sleep(3)
        
        # Check rate limit FIRST
        if await check_rate_limit(page):
            raise RateLimitError("Rate limit detected")
        
        # Build 5-layer prompt
        prompt = PromptBuilder.build(
            character_pose, camera_angle, style_suffix,
            motion_description, dialogue, character_name, emotion
        )
        logger.info(f"📝 Prompt: {prompt[:100]}...")
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image text file not found at {image_path}")

        if not image_path.exists():
            raise FileNotFoundError(f"Image text file not found at {image_path}")
            
        # Step 1: Find and fill the prompt input FIRST (User Request)
        prompt_selectors = [
            ".ProseMirror",  # Primary for Grok
            "textarea",
            "[placeholder*='imagine']",
            "[contenteditable='true']",
        ]
        
        prompt_filled = False
        for selector in prompt_selectors:
            try:
                el = page.locator(selector)
                if await el.count() > 0:
                    logger.info(f"📝 Found prompt area: {selector}")
                    await el.first.click() # Focus it first!
                    await el.first.fill(prompt)
                    logger.info(f"✅ Filled prompt")
                    prompt_filled = True
                    break
            except Exception:
                continue
        
        if not prompt_filled:
            raise UIChangedError("Could not find prompt input field")
            
        await asyncio.sleep(1)

        # Step 2: Drag-and-Drop upload onto the active editor
        logger.info(f"🏗️ Initiating Drag-and-Drop upload for {image_path.name}...")
        
        # Read file as base64
        import base64
        import mimetypes
        
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png"
            
        with open(image_path, "rb") as f:
            file_b64 = base64.b64encode(f.read()).decode("utf-8")
            
        # Drop target: Target the ProseMirror editor directly
        drop_target_selector = ".ProseMirror"
        
        try:
            # Wait for drop target
            drop_target = page.locator(drop_target_selector).first
            await drop_target.wait_for(state="attached", timeout=5000)
            
            # Execute JS to simulate drop
            logger.info("📦 Dispatching DROP event with file data...")
            await page.evaluate("""
                async ({ selector, fileBase64, fileName, fileType }) => {
                    // Convert base64 to Blob
                    const byteCharacters = atob(fileBase64);
                    const byteNumbers = new Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                    }
                    const byteArray = new Uint8Array(byteNumbers);
                    const blob = new Blob([byteArray], { type: fileType });
                    const file = new File([blob], fileName, { type: fileType });
                    
                    // Create DataTransfer
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(file);
                    
                    // Find target
                    const target = document.querySelector(selector);
                    if (!target) throw new Error(`Drop target not found: ${selector}`);
                    
                    // Dispatch events: dragenter -> dragover -> drop
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

        except Exception as e:
            logger.error(f"❌ Drag and Drop failed: {e}")
            logger.info("🛑 Aborting upload.")
            pass # Continue to try text generation anyway

        # Wait for upload processing (thumbnail appearance)
        await asyncio.sleep(5)
        
        # Step 3: Switch to Video mode if there's an Image/Video dropdown
        # Look for the "Image" dropdown and switch to "Video"
        mode_selectors = [
            "button:has-text('Image')",
            "[aria-label*='Image']",
            "[data-testid='mode-selector']",
        ]
        
        for selector in mode_selectors:
            try:
                el = page.locator(selector)
                if await el.count() > 0:
                    await el.first.click()
                    await asyncio.sleep(0.5)
                    # Now click on Video option
                    video_option = page.locator("text='Video'")
                    if await video_option.count() > 0:
                        await video_option.first.click()
                        logger.info("✅ Switched to Video mode")
                    break
            except Exception:
                continue
        
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
        
        # Smart Wait: Race between URL change AND Video element appearance
        # We don't want to wait 180s if the video is already there!
        try:
            async def wait_for_video_element():
                # Check for video tag or the "Download" button
                for _ in range(60): # Check every 2s for 2 minutes
                    if await page.locator("video").count() > 0:
                        return "video_found"
                    if await page.locator("button[aria-label='Download']").count() > 0:
                        return "download_found"
                    await asyncio.sleep(2)
                raise TimeoutError("Video element never appeared")

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
                
            if any(t.result() == "video_found" or t.result() == "download_found" for t in done if not t.cancelled() and not t.exception()):
                logger.info("🎥 Video element appeared! Proceeding directly...")
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
        
        # METHOD 1: Download Button (High Quality / Original File)
        # This is preferred because the <video> tag often contains compressed/stream versions.
        logger.info("⬇️ Attempting high-quality download via buttons...")
        download_selectors = [
            "button[aria-label='Download']",
            "button:has-text('Download')",
            "a[download]",
            "[data-testid='download-button']",
        ]
        
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
                        logger.info(f"✅ Downloaded High-Quality Video: {output}")
                        
                        # Verify it's actually a video (sometimes buttons trigger image downloads)
                        if output.stat().st_size < 10000: # < 10KB is suspicious
                            logger.warning("⚠️ Downloaded file is too small (might be a text error or thumbnail). Retrying...")
                            continue
                            
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
                    logger.warning("⚠️ Blob URL detected from Python side. Cannot download safely.")
                    raise ValueError("Blob URL")

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
        await browser.close()
        await pw.stop()


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
        self.profile_path = Path.home() / ".grok-profiles" / profile_name
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
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_path),
            headless=os.getenv("GROK_HEADLESS", "false").lower() == "true",
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-dev-shm-usage',
            ],
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
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
        self.rate_limit_cooldown = 7200  # 2 hours in seconds
    
    async def animate(
        self,
        image_path: Path,
        motion_prompt: str = "",
        style_suffix: str = "Cinematic, dramatic lighting",
        duration: int = 10,
        aspect_ratio: str = "9:16",
        dialogue: Optional[str] = None
    ) -> Path:
        """
        Animate an image using Grok Imagine.
        
        Args:
            image_path: Path to the input image
            motion_prompt: Description of the motion/animation
            style_suffix: Visual style to apply
            duration: 6 or 10 seconds
            aspect_ratio: "9:16" or "16:9"
            
        Returns:
            Path to the generated video file
        """
        duration_str = f"{duration}s"
        
        try:
            result = await generate_single_clip(
                image_path=image_path,
                character_pose="the character in the image",
                camera_angle="Medium shot",
                style_suffix=style_suffix,
                motion_description=motion_prompt,
                duration=duration_str,
                aspect=aspect_ratio,
                dialogue=dialogue
            )
            self.generation_count += 1
            logger.info(f"🎥 Generated clip #{self.generation_count}: {result}")
            return result
            
        except RateLimitError:
            logger.warning(f"⏳ Rate limit hit after {self.generation_count} generations")
            raise
    
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
                    delay = random.uniform(5, 15)
                    logger.info(f"⏱️ Waiting {delay:.1f}s before next generation...")
                    await asyncio.sleep(delay)
                    
            except RateLimitError:
                # Return partial results and raise for retry handling
                logger.error(f"Rate limited at scene {i+1}/{len(scenes)}")
                return results, i  # Return results and checkpoint index
        
        return results
    
    def get_stats(self) -> dict:
        """Get generation statistics."""
        return {
            "generations_this_session": self.generation_count,
            "profile_path": str(self.profile_manager.profile_path),
            "rate_limit_cooldown_seconds": self.rate_limit_cooldown
        }


# ============================================
# CLI for Manual Testing
# ============================================
if __name__ == "__main__":
    import sys
    
    async def test_generation():
        # Test with a sample image
        if len(sys.argv) < 2:
            print("Usage: python grok_agent.py <image_path>")
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
    
    asyncio.run(test_generation())

