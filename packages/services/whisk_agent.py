
"""
Google Whisk Agent for Image Generation.

Replaces API-based generation with browser automation of labs.google/fx/tools/whisk.
Supports:
- Persistent Login (Manual first time, then automated)
- Aspect Ratio Switching (16:9 vs 9:16)
- High Quality Downloads
"""
import os
import asyncio
import random
import logging
from pathlib import Path
from uuid import uuid4
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError

logger = logging.getLogger(__name__)

# Use the same profile root as Grok to potentially share Google Auth if possible,
# or keep them separate but managed similarly.
PROFILE_PATH = Path.home() / ".whisk-profile"

class WhiskAgent:
    """
    Automates Google Whisk for image generation.
    """
    _lock = asyncio.Lock() # Class-level lock to prevent concurrent profile access
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.profile_path = PROFILE_PATH
        self.profile_path.mkdir(parents=True, exist_ok=True)
        self.browser = None
        self.pw = None
        self.page = None
        
    async def get_context(self) -> tuple[BrowserContext, any]:
        """Launch browser with persistent profile with retries."""
        playwright = await async_playwright().start()
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-infobars',
            '--start-maximized'
        ]
        
        # Retry logic for profile lock
        for attempt in range(3):
            try:
                browser = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_path),
                    channel="chrome",
                    headless=self.headless,
                    args=args,
                    viewport=None,
                    timeout=30000
                )
                return browser, playwright
            except Exception as e:
                if "user data directory is already in use" in str(e).lower() and attempt < 2:
                    logger.warning(f"⚠️ Profile locked (attempt {attempt+1}/3). Waiting...")
                    await asyncio.sleep(5)
                    continue
                raise e

    async def close(self):
        """Close browser and stop playwright. Shared lock to ensure profile is clean."""
        async with WhiskAgent._lock:
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
                self.browser = None
            if self.pw:
                try:
                    await self.pw.stop()
                except:
                    pass
                self.pw = None
            self.page = None

    async def generate_image(
        self, 
        prompt: str, 
        is_shorts: bool = False,
        style_suffix: str = "",
        page: Optional[Page] = None,
        character_paths: list[Path] = [],
        style_image_path: Optional[Path] = None
    ) -> bytes:
        """
        Generate a single image.
        Accepts optional 'page' to reuse existing browser session (critical for bulk).
        """
        # If we are managing the full lifecycle, wrap the whole thing in a lock
        # to ensure the profile is free and consistent.
        if not page:
            async with WhiskAgent._lock:
                return await self._generate_image_impl(prompt, is_shorts, style_suffix, character_paths, style_image_path=style_image_path)
        else:
            return await self._generate_image_impl(prompt, is_shorts, style_suffix, character_paths, page=page, style_image_path=style_image_path)

    async def _generate_image_impl(
        self, 
        prompt: str, 
        is_shorts: bool = False,
        style_suffix: str = "",
        character_paths: list[Path] = [],
        style_image_path: Optional[Path] = None,
        page: Optional[Page] = None
    ) -> bytes:
        """Internal implementation of generate_image."""
        browser = None
        pw = None
        
        # If page not provided, creating full context (Single Shot)
        if not page:
            if not self.browser:
                self.browser, self.pw = await self.get_context()
            if not self.page:
                self.page = await self.browser.new_page()
            page = self.page
            await page.goto("https://labs.google/fx/tools/whisk/project", timeout=60000)
        
        try:
            # Check for login requirement
            if "Sign in" in await page.title() or await page.locator("text='Sign in'").count() > 0:
                logger.error("🛑 Whisk requires login! Please run the login helper script first.")
                raise RuntimeError("Authentication required. Run 'python scripts/auth_whisk.py'")

            # 0. Fast-path: Sidebar Opening (User wants this clicked within 2s)
            if character_paths:
                logger.info("⚡ Attempting immediate sidebar open...")
                sidebar_trigger = page.get_by_text("ADD IMAGES")
                try:
                    # Wait for the trigger to appear (extended to 3s per user request)
                    await sidebar_trigger.wait_for(state="attached", timeout=3000)
                    await sidebar_trigger.first.click(force=True)
                    logger.info("✅ Clicked ADD IMAGES inside 3s window.")
                    # Let it animate while we do other things
                except Exception:
                    logger.info("Sidebar trigger not found instantly, will retry in background flow.")

            # 1. Wait for the main interface (textarea)
            textarea = page.locator("textarea[placeholder*='Describe your idea']")
            try:
                await textarea.wait_for(state="visible", timeout=30000)
            except TimeoutError:
                logger.error("❌ Could not find Whisk prompt input.")
                raise UIChangedError("Whisk UI not loaded.")

            # 2. Set Aspect Ratio
            target_aspect = "Portrait" if is_shorts else "Landscape"
            logger.info(f"📐 Setting Aspect Ratio: {target_aspect}")
            
            aspect_btn = page.locator("button").filter(has_text="aspect_ratio")
            
            if await aspect_btn.count() > 0:
                await aspect_btn.first.click()
                if is_shorts:
                    await page.locator("text='9:16'").click()
                else:
                    await page.locator("text='16:9'").click()
                
                await page.mouse.click(10, 10)
                await asyncio.sleep(0.5)

            # 3. Handle Character Consistency (Side Panel)
            if character_paths or style_image_path:
                # Ensure sidebar is actually open (if step 0 failed)
                if await page.locator("h4", has_text="Subject").count() == 0:
                    sidebar_trigger = page.get_by_text("ADD IMAGES")
                    if await sidebar_trigger.count() > 0:
                        await sidebar_trigger.first.click(force=True)
                        await asyncio.sleep(0.8)

                # --- 3a. Handle SUBJECTS (Characters) ---
                # --- Unified Helper for Sections ---
                async def upload_to_section(section_key: str, files: list[Path], wait_time: int = 5):
                    logger.info(f"Scanning for '{section_key}' section input...")
                    
                    # --- SLOT MANAGEMENT (Subject Only) ---
                    if section_key == "Subject" and len(files) > 1:
                        # 1. Count existing slots for Subject
                        subject_header = page.locator("h4, h3, .section-header").filter(has_text="Subject").first
                        if await subject_header.count() > 0:
                            # Find the container or sibling inputs
                            # We assume standard layout: Header -> Container -> Slot(s)
                            # Strategy: Click the (+) button until we have enough slots
                            plus_btn = page.locator("i:text('control_point')") # The plus icon
                            if await plus_btn.count() > 0:
                                # For now, safe heuristic: Click (+) (len(files) - 1) times if we are just starting?
                                clicks_needed = len(files) - 1
                                if clicks_needed > 0:
                                    logger.info(f"➕ Need {clicks_needed} extra Subject slots. Clicking '+'...")
                                    for _ in range(clicks_needed):
                                        if await plus_btn.first.is_visible():
                                            await plus_btn.first.click()
                                            await asyncio.sleep(0.5)
                    
                    all_inputs = page.locator("input[type='file']")
                    target_inp = None
                    
                    for i in range(await all_inputs.count()):
                        inp = all_inputs.nth(i)
                        # JS to find the closest preceding header (h3, h4, or class)
                        header_text = await page.evaluate('''(element) => {
                            function getHeader(node) {
                                let curr = node;
                                while (curr) {
                                    if (curr.previousElementSibling) {
                                        curr = curr.previousElementSibling;
                                        if (curr.matches && (curr.matches('h4') || curr.matches('h3') || curr.matches('.section-header'))) return curr.innerText;
                                        let h = curr.querySelector('h4, h3, .section-header');
                                        if (h) return h.innerText;
                                    } else {
                                        curr = curr.parentElement;
                                        if (!curr || curr.tagName === 'BODY') return null;
                                    }
                                }
                                return null;
                            }
                            return getHeader(element);
                        }''', await inp.element_handle())
                        
                        if header_text and section_key.upper() in header_text.upper():
                            logger.info(f"✅ Found {section_key} input (Header: '{header_text}')")
                            target_inp = inp
                            break
                    
                    if target_inp:
                        try:
                            await target_inp.set_input_files(files)
                            logger.info(f"📤 Uploaded {len(files)} files to {section_key}. Waiting {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            return True
                        except Exception as e:
                            logger.error(f"❌ Failed to upload to {section_key}: {e}")
                            return False
                    else:
                        logger.warning(f"⚠️ Could not find input for section '{section_key}'")
                        return False

                # --- 3a. Handle SUBJECTS (Characters) ---
                if character_paths:
                    if not await upload_to_section("Subject", character_paths, wait_time=6 + (len(character_paths) * 3)):
                        # Fallback for Subject only (Critical)
                         logger.warning("Trying fallback for Subject (First Input)...")
                         all_inputs = page.locator("input[type='file']")
                         if await all_inputs.count() > 0:
                             await all_inputs.first.set_input_files(character_paths)
                             await asyncio.sleep(8)

                # --- 3b. Handle STYLE Image ---
                if style_image_path:
                    # Style is often the second input, or explicitly labeled
                    await upload_to_section("Style", [style_image_path], wait_time=6)

            # 2. Enter Prompt
            clean_prompt = prompt.strip()
            if clean_prompt.endswith('.'):
                clean_prompt = clean_prompt[:-1].strip()
            
            clean_style = style_suffix.strip()
            if clean_style.startswith(','):
                clean_style = clean_style[1:].strip()
                
            full_prompt = clean_prompt
            if clean_style:
                full_prompt += f", {clean_style}"
            
            # Clear previous text
            await textarea.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            
            await textarea.fill(full_prompt)
            await asyncio.sleep(1.0)
            
            # 3. Click Generate / Submit
            # --- SNAPSHOT LOGIC: Count existing images to detect NEW generation ---
            initial_image_count = 0
            try:
                pre_imgs = page.locator("img")
                for i in range(await pre_imgs.count()):
                    if await pre_imgs.nth(i).is_visible():
                         box = await pre_imgs.nth(i).bounding_box()
                         if box and box['width'] > 200 and box['height'] > 200:
                             initial_image_count += 1
                logger.info(f"📸 Initial Valid Images: {initial_image_count}")
            except: pass

            submit_btn = page.locator("button:has(i)").filter(has_text="arrow_forward")
            if await submit_btn.count() == 0:
                 submit_btn = page.locator("button[aria-label='Submit prompt'], button[aria-label='Generate']")
            
            async def perform_submit():
                if await submit_btn.count() > 0:
                    btn = submit_btn.first
                    # Wait for disabled attribute to vanish
                    for _ in range(6): 
                        is_disabled = await btn.get_attribute("disabled")
                        if is_disabled is None: break
                        await asyncio.sleep(0.5)
                    try:
                        await btn.click(timeout=5000)
                        logger.info("🚀 Clicked 'Submit'")
                    except:
                        await btn.evaluate("el => el.click()")
                        logger.info("🚀 Clicked 'Submit' (JS Fallback)")
                    return True
                return False

            if not await perform_submit():
                logger.warning("⚠️ Specific 'arrow_forward' button not found. Trying last icon-button...")
                possible_btns = page.locator("button:has(svg), button:has(i)")
                count = await possible_btns.count()
                if count > 0:
                     await possible_btns.nth(count - 1).click()
                     logger.info("🚀 Clicked last icon-button (Blind Guess)")
                else:
                    logger.error("❌ Could not find ANY Generate/Submit button!")

            # 4. Wait for Generation
            logger.info("⏳ Waiting for image generation...")
            
            start_time = asyncio.get_event_loop().time()
            max_wait = 45 
            found_generation = False
            submit_retry_done = False
            
            while asyncio.get_event_loop().time() - start_time < max_wait:
                try:
                    # 0. Check if page is closed (avoid TargetClosedError)
                    if page.is_closed():
                        logger.warning("⚠️ Page was closed unexpectedly.")
                        break

                    # 1. Count large images (Results) - CHECK THIS FIRST
                    potential_imgs = page.locator("img")
                    count = await potential_imgs.count()
                    large_count = 0
                    for i in range(count):
                        try:
                            img = potential_imgs.nth(i)
                            if await img.is_visible():
                                box = await img.bounding_box()
                                if box and box['width'] > 200 and box['height'] > 200:
                                    large_count += 1
                        except: continue
                    
                    if large_count > initial_image_count:
                        logger.info(f"✅ Detected new image (Total: {large_count} > Initial: {initial_image_count}). Proceeding...")
                        found_generation = True
                        break

                    # 2. Check if page is still on the correct URL (not redirected to home)
                    if "whisk" not in page.url.lower():
                        logger.warning(f"⚠️ Unexpected redirect detected: {page.url[:50]}")
                        break

                    if page.is_closed():
                        logger.warning("⚠️ Page connection lost (is_closed=True). Exiting loop.")
                        break

                    # 3. Check for real visible "Oops" popup ONLY if no images found yet
                    error_check = await page.evaluate('''() => {
                        const oopsElements = Array.from(document.querySelectorAll('div, span, p'))
                            .filter(el => {
                                if (!el.innerText || !el.innerText.includes("Oops, something went wrong")) return false;
                                const rect = el.getBoundingClientRect();
                                const isVisible = rect.width > 0 && rect.height > 0 && 
                                                 window.getComputedStyle(el).visibility !== 'hidden' &&
                                                 window.getComputedStyle(el).display !== 'none';
                                const isSmall = rect.width < 600 && rect.height < 200;
                                const isNotGiant = el.innerText.length < 200;
                                return isVisible && isSmall && isNotGiant;
                            });
                        return oopsElements.length > 0 ? oopsElements[0].innerText : null;
                    }''')
                    if error_check:
                        # RETRY STRATEGY: If "Oops" appears early (submission failure), try re-submitting once.
                        if (asyncio.get_event_loop().time() - start_time) < 10 and not submit_retry_done:
                            logger.warning("⚠️ Oops appeared early (Submission issue). Retrying Submit in 5s...")
                            await asyncio.sleep(5)
                            await perform_submit()
                            submit_retry_done = True
                            continue # Reset loop check for images

                        # Give it one more short sleep to see if images appear (sometimes toast is transient)
                        await asyncio.sleep(2.0)
                        potential_imgs = page.locator("img")
                        count = await potential_imgs.count()
                        for i in range(count):
                            try:
                                img = potential_imgs.nth(i)
                                if await img.is_visible():
                                    box = await img.bounding_box()
                                    if box and box['width'] > 200 and box['height'] > 200:
                                        large_count += 1
                            except: continue
                        
                        if large_count > initial_image_count:
                            logger.info(f"✅ Images appeared after Oops toast. Proceeding...")
                            found_generation = True
                            break
                            
                        logger.error(f"❌ Whisk reported a failure: {error_check}")
                        raise RuntimeError(f"Whisk error: {error_check}")
                except RuntimeError as e:
                    # Re-raise explicit whisk errors
                    if "Whisk error" in str(e): raise e
                except Exception as e:
                    if "closed" in str(e).lower():
                        logger.warning("⚠️ Page connection lost during polling. Exiting loop.")
                        break
                    logger.debug(f"Polling check failed: {e}")
                    
                await asyncio.sleep(1.5)
            
            if not found_generation:
                logger.warning("⚠️ Generation timeout or no images found.")

            # 5. Download Strategy
            # Use the download button if available for better quality, otherwise fallback to img src
            # Filter for "Main" images (large enough) to avoid icons/avatars
            # And usually the Result is the LAST valid image (Right side)
            
            # Short wait for final render stabilize
            await asyncio.sleep(0.5)
            
            # Results are often blob: URLs now
            if page.is_closed():
                logger.error("❌ Page closed before download could start.")
                raise RuntimeError("Browser page closed during download phase.")
                
            try:
                potential_images = page.locator("img")
                count = await potential_images.count()
            except Exception as e:
                logger.error(f"❌ Error accessing images: {e}")
                raise RuntimeError(f"Failed to access generated images: {e}")
            
            target_img = None
            valid_images = []
            
            for i in range(count):
                img = potential_images.nth(i)
                try:
                    box = await img.bounding_box()
                    # Filter: Must be substantial size (e.g. > 150px)
                    if box and box['width'] > 150 and box['height'] > 150:
                        valid_images.append(img)
                except:
                    continue
            
            if valid_images:
                logger.info(f"📸 Found {len(valid_images)} valid images (large size). Selecting the LAST one (Right).")
                target_img = valid_images[-1] # User specified "Right one", which is usually last in DOM
            else:
                logger.warning("⚠️ No large images found. Cannot download results.")
                raise RuntimeError("No large images found after generation. Check for errors in the browser.")
            
            if target_img:
                # Hover over the image to reveal buttons
                await target_img.scroll_into_view_if_needed()
                await target_img.hover()
                await asyncio.sleep(0.5) # Wait for hover toolbar animation
                
                # Try multiple possible download button selectors
                download_btn = page.locator("button:has(i:text('download')), button[aria-label*='Download']").last
                
                if await download_btn.count() > 0 and await download_btn.is_visible():
                    logger.info("💾 Found 'download' button! Triggering download...")
                    async with page.expect_download() as download_info:
                        await download_btn.evaluate("el => el.click()")
                    
                    download = await download_info.value
                    temp_path = await download.path()
                    if temp_path:
                        with open(temp_path, "rb") as f:
                            return f.read()
                
                # FALLBACK: JS Fetch (Works for blob: and https: in page context)
                logger.warning("⚠️ UI download failed. Attempting robust JS Fetch...")
                src = await target_img.get_attribute("src")
                if src:
                    try:
                        # Fetch the image in the page context and return as base64
                        b64_data = await page.evaluate('''(url) => {
                            return fetch(url)
                                .then(response => response.blob())
                                .then(blob => new Promise((resolve, reject) => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                    reader.onerror = reject;
                                    reader.readAsDataURL(blob);
                                }));
                        }''', src)
                        import base64
                        return base64.b64decode(b64_data)
                    except Exception as e:
                        logger.error(f"❌ JS Fetch failed: {e}")
            
            raise RuntimeError("Failed to extract image result from Whisk")

        finally:
            # We don't auto-close anymore to allow the caller to decide (especially for reuse)
            pass

    async def generate_batch(
        self,
        prompts: list[str],
        is_shorts: bool = False,
        style_suffix: str = "",
        delay_seconds: int = 5,
        character_paths: list[Path] = []
    ) -> list[bytes]:
        """
        Generate multiple images in a single session (Bulk Mode).
        Performs high-speed bulk generation natively.
        """
        results = []
        if not self.browser:
            self.browser, self.pw = await self.get_context()
        try:
            page = await self.browser.new_page()
            await page.goto("https://labs.google/fx/tools/whisk/project", timeout=60000)
            
            err_count = 0
            for i, prompt in enumerate(prompts):
                logger.info(f"🔄 Bulk Generation {i+1}/{len(prompts)}")
                
                # SANITIZATION: Strict "One Line = One Image" Rule
                # Replace any internal newlines with spaces to prevent job fragmentation
                clean_prompt = prompt.replace("\n", " ").replace("\r", " ").strip()
                
                try:
                    img_bytes = await self.generate_image(
                        clean_prompt, 
                        is_shorts, 
                        style_suffix, 
                        page=page, # Pass the existing page object
                        character_paths=character_paths if i == 0 else [] # Upload ONCE per session
                    )
                    results.append(img_bytes)
                    
                    # Wait between generations
                    logger.info(f"💤 Waiting {delay_seconds}s...")
                    await asyncio.sleep(delay_seconds)
                    err_count = 0 # Reset error count on success
                    
                except Exception as e:
                    logger.error(f"❌ Failed to generate prompt {i+1}: {e}")
                    results.append(None) # Place holder
                    err_count += 1
                    if err_count > 3:
                        logger.error("🛑 Too many consecutive errors. Aborting bulk run.")
                        break
                        
            return results
        finally:
            await self.close()

class UIChangedError(Exception):
    pass
