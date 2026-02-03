
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
import logging
import re  # Added for regex header matching
from pathlib import Path
from uuid import uuid4
from typing import Optional, Union, List

from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError

logger = logging.getLogger(__name__)

# Use the same profile root as Grok to potentially share Google Auth if possible,
# or keep them separate but managed similarly.
PROFILE_PATH = Path.home() / ".whisk-profile"

class WhiskAgent:
    """
    Automates Google Whisk for image generation.
    """
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.profile_path = PROFILE_PATH
        self.profile_path.mkdir(parents=True, exist_ok=True)
        self.browser = None
        self.pw = None
        self.page = None
        logger.info("🦄 WhiskAgent initialized (Sequence Flow v3.1 - Style First + Scene Debug)")
        
    async def get_context(self) -> tuple[BrowserContext, any]:
        """Launch browser with persistent profile."""
        playwright = await async_playwright().start()
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-infobars',
            '--start-maximized'
        ]
        
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_path),
            channel="chrome",
            headless=self.headless,
            args=args,
            viewport=None, # Use actual window size
        )
        return browser, playwright

    async def close(self):
        """Close browser and stop playwright."""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.pw:
            await self.pw.stop()
            self.pw = None
        self.page = None

    async def _find_input_for_section(self, page: Page, section_name: str) -> Optional[object]:
        """Finds a file input associated with a specific section header using JS traversal."""
        return await page.evaluate(f'''(sectionName) => {{
            const headers = Array.from(document.querySelectorAll("h1, h2, h3, h4, div"));
            const targetHeader = headers.find(h => h.innerText.trim().toUpperCase().includes(sectionName));
            if (!targetHeader) return null;
            
            // Find all file inputs
            const inputs = Array.from(document.querySelectorAll("input[type='file']"));
            
            // Find the input that belongs to this header
            // Logic: The input should be "after" this header and "before" the next significant header
            
            let bestInput = null;
            let minDistance = Infinity;
            
            const headerRect = targetHeader.getBoundingClientRect();
            
            for (const input of inputs) {{
                const inputRect = input.getBoundingClientRect();
                
                // Must be below the header
                if (inputRect.y > headerRect.y) {{
                    const distance = inputRect.y - headerRect.y;
                    
                    // Check if there's another header in between
                    // (This is a simplified check, ideally we'd check DOM structure)
                    if (distance < minDistance) {{
                         bestInput = input;
                         minDistance = distance;
                    }}
                }}
            }}
            return bestInput; // Returns the DOM element handle (which Playwright converts)
        }}''', section_name)

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

            # 1.4 Ensure Sidebar is open for any uploads
            logger.info(f"DEBUG: style_image_path={style_image_path}, character_paths_len={len(character_paths) if character_paths else 0}")
            if style_image_path or character_paths:
                # Check for "Subject" or "Style" header to see if sidebar is open
                sidebar_elements = page.locator("h4").filter(has_text=re.compile(r"Subject|Style", re.I))
                sidebar_count = await sidebar_elements.count()
                logger.info(f"DEBUG: Sidebar elements count: {sidebar_count}")
                
                if sidebar_count == 0:
                    logger.info("Opening sidebar (ADD IMAGES button)...")
                    sidebar_trigger = page.get_by_text("ADD IMAGES")
                    if await sidebar_trigger.count() > 0:
                        await sidebar_trigger.first.click(force=True)
                        await asyncio.sleep(2) # Wait for animation and loading
                    else:
                        logger.warning("⚠️ Could not find 'ADD IMAGES' trigger button!")
                else:
                    logger.info("Sidebar already appears open.")

            # 1.5 Upload Style Image (PHASE 1)
            if style_image_path:
                exists = style_image_path.exists() if hasattr(style_image_path, "exists") else False
                logger.info(f"🚀 PHASE 1 START: Style Image Upload. Path: {style_image_path}. Exists: {exists}")
                
                if exists:
                    try:
                        # Scroll to ensure Style section is visible inside sidebar
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(1)

                        # Strategy A: Find button by text (Case Insensitive)
                        # We use regex to match "UPLOAD IMAGE" regardless of case/transform
                        upload_btn = page.locator("button, div, span").filter(has_text=re.compile(r"UPLOAD IMAGE", re.I)).last
                        
                        btn_count = await upload_btn.count()
                        logger.info(f"DEBUG: 'UPLOAD IMAGE' button count: {btn_count}")

                        if btn_count > 0:
                            logger.info("Found upload button. Clicking via File Chooser...")
                            async with page.expect_file_chooser(timeout=30000) as fc_info:
                                await upload_btn.click(force=True)
                            file_chooser = await fc_info.value
                            await file_chooser.set_input_files(style_image_path)
                            logger.info("✅ SUCCESS: Uploaded via button click.")
                        else:
                            logger.warning("⚠️ 'UPLOAD IMAGE' button not found. Trying icons/fallbacks...")
                            # Strategy B: Find via icons (stylus_note)
                            icons = page.locator("i").filter(has_text=re.compile(r"stylus_note|location_on", re.I))
                            logger.info(f"DEBUG: Found {await icons.count()} potential section icons.")
                            
                            target_input = page.locator("div").filter(has=page.locator("i", has_text=re.compile(r"stylus_note|location_on", re.I))).locator("input[type='file']").first
                            if await target_input.count() > 0:
                                await target_input.set_input_files(style_image_path)
                                logger.info("✅ SUCCESS: Uploaded via icon-scoped input.")
                            else:
                                # Strategy C: Global last resort
                                all_inputs = page.locator("input[type='file']")
                                input_count = await all_inputs.count()
                                logger.info(f"DEBUG: Global file inputs count: {input_count}")
                                if input_count > 0:
                                    logger.info("Using global last-resort file input...")
                                    await all_inputs.last.set_input_files(style_image_path)
                                    logger.info("✅ SUCCESS: Uploaded via global fallback.")
                                else:
                                    logger.error("❌ CRITICAL: No file inputs found on page!")

                        # ALWAYS wait for analysis
                        logger.info("⏳ Waiting 20 seconds for analysis (Style Phase Pause)...")
                        await asyncio.sleep(20)
                            
                    except Exception as e:
                        logger.error(f"❌ ERROR in Style Upload Phase: {e}")
                        await asyncio.sleep(5)
                else:
                    logger.warning(f"⚠️ Skipping Phase 1: Style file does not exist at {style_image_path}")
            else:
                logger.info("ℹ️ Skipping Phase 1: No style_image_path provided for this scene.")

            # 3. Handle Character Consistency (Side Panel)
            if character_paths:
                logger.info("🚀 PHASE 2: Subject Image Uploads")
                
                # Check for "Subject" header
                subject_header = page.locator("h4").filter(has_text="Subject").first
                if await subject_header.count() > 0:
                    logger.info("Found Subject section header.")
                    
                    for i, char_path in enumerate(character_paths):
                        logger.info(f"Handling Character Consistency {i+1}/{len(character_paths)}: {char_path.name}")
                        
                        # Find potential slots specifically within the sidebar that have a person icon.
                        slots = page.locator("div:has(i:text('person'))").filter(has_not=page.locator("h1, h2, h3, h4"))
                        slot_count = await slots.count()
                        logger.info(f"Detected {slot_count} slots.")
                        
                        # If we need more slots, click the 'control_point' button in the Subject section.
                        if i >= slot_count:
                            logger.info("Adding new Subject category...")
                            add_btn = page.locator("div").filter(has=page.locator("h4", has_text="Subject")).locator("button[aria-label='Add new category'], button:has(i:text('control_point'))").first
                            if await add_btn.count() == 0:
                                add_btn = page.locator("button[aria-label='Add new category'], button:has(i:text('control_point'))").first
                                
                            await add_btn.click()
                            await asyncio.sleep(2)
                            slots = page.locator("div:has(i:text('person'))").filter(has_not=page.locator("h1, h2, h3, h4"))
                            slot_count = await slots.count()

                        target_slot = slots.nth(i)
                        
                        try:
                            # 1. Direct file setting
                            logger.info(f"Checking for hidden file input in slot {i+1}...")
                            hidden_input = target_slot.locator("input[type='file']")
                            if await hidden_input.count() > 0:
                                logger.info("Uploading via direct file setting on hidden input...")
                                await hidden_input.first.set_input_files(char_path)
                            else:
                                # 2. Hover Lower Part as fallback
                                logger.info("No file input found, trying hover-reveal...")
                                await target_slot.scroll_into_view_if_needed()
                                box = await target_slot.bounding_box()
                                if box:
                                    await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height'] * 0.85)
                                    await asyncio.sleep(1.2)
                                else:
                                    await target_slot.hover()
                                    await asyncio.sleep(1.2)
                                
                                # Target the "Upload Image" button revealed by hover
                                upload_btn = page.locator("button:has-text('Upload Image')").nth(i)
                                async with page.expect_file_chooser(timeout=30000) as fc_info:
                                    await upload_btn.click(force=True)
                                file_chooser = await fc_info.value
                                await file_chooser.set_input_files(char_path)
                                logger.info("Uploaded via revealed button.")
                            
                            await asyncio.sleep(6) # Processing delay
                        except Exception as e:
                            logger.error(f"Failed character upload {i+1}: {e}")
                            # Last chance fallback
                            try:
                                all_inputs = page.locator("input[type='file']")
                                if await all_inputs.count() > i:
                                    await all_inputs.nth(i).set_input_files(char_path)
                                    await asyncio.sleep(5)
                            except: pass
                    
                    # Wait for Whisk to analyze the uploaded characters
                    logger.info("Waiting 5 seconds after Subject upload...")
                    await asyncio.sleep(5)



            # 2. Enter Prompt
            full_prompt = f"{prompt}, {style_suffix}".strip()
            
            # Ensure textarea is ready (sometimes analysis locks it)
            await textarea.wait_for(state="visible", timeout=10000)
            await textarea.click()
            
            # Clear previous text
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            
            # Type slowly regarding "text is too small" -> likely means "too fast" or race condition
            # Increased delay to 100ms per user feedback
            await textarea.type(full_prompt, delay=100) 
            await asyncio.sleep(1)


            
            # 3. Click Generate / Submit
            # Wait a moment for validation/UI to update after typing
            await asyncio.sleep(2)
            
            # Strategy A: User's confirmed HTML (<button><i>arrow_forward</i></button>)
            # Also try aria-label as it's often present
            submit_btn = page.locator("button:has(i)").filter(has_text="arrow_forward")
            
            if await submit_btn.count() == 0:
                 submit_btn = page.locator("button[aria-label='Submit prompt'], button[aria-label='Generate']")
            
            if await submit_btn.count() > 0:
                submit_btn = submit_btn.first # Take the first if multiple
                logger.info("Found 'Submit' button. Checking state...")
                
                # Wait for disabled attribute to vanish
                for _ in range(10): # retry for 5 seconds
                    is_disabled = await submit_btn.get_attribute("disabled")
                    if is_disabled is None:
                        logger.info("✅ Button is active!")
                        break
                    logger.info("⏳ Button still disabled/validating...")
                    await asyncio.sleep(0.5)
                
                # Force Click using JavaScript (Bypasses overlays/hit-tests)
                try:
                    await submit_btn.evaluate("el => el.click()")
                    logger.info("🚀 Clicked 'Submit' (via JS force-click)")
                except Exception as e:
                     logger.warning(f"JS Click failed: {e}. Trying standard click...")
                     await submit_btn.click(force=True)
            
            else:
                logger.warning("⚠️ Specific 'arrow_forward' button not found. Trying generics...")
                # Strategy C: The Big Arrow Button is usually the last button with an SVG or Icon in the main area
                # We can target the circle button class if we knew it, but last button is a decent guess for "Send"
                possible_btns = page.locator("button:has(svg), button:has(i)")
                count = await possible_btns.count()
                if count > 0:
                     last_btn = possible_btns.nth(count - 1)
                     await last_btn.click()
                     logger.info("🚀 Clicked last available icon-button (Blind Guess)")
                else:
                    logger.error("❌ Could not find ANY Generate/Submit button!")

            # 4. Wait for Generation
            logger.info("⏳ Waiting for image generation...")
            # Ideally detect the spinner or new image appearing
            await asyncio.sleep(12) 
            
            # 5. Download Strategy
            # Use the download button if available for better quality, otherwise fallback to img src
            images = page.locator("img[src^='https://']")
            count = await images.count()
            if count > 0:
                # Hover over the last image to reveal buttons
                last_img = images.nth(count - 1)
                await last_img.hover()
                await asyncio.sleep(0.5)
                
                # User's provided HTML for download button contains <i>download</i>
                # The button is often in a toolbar that appears on hover
                download_btn = page.locator("button:has(i)").filter(has_text="download").last
                
                if await download_btn.count() > 0:
                    logger.info("💾 Found 'download' button! Triggering download...")
                    # Sometimes the button needs a real hover/click to register
                    await download_btn.scroll_into_view_if_needed()
                    
                    async with page.expect_download() as download_info:
                        # Use JS click as it's more reliable for these floating menus
                        await download_btn.evaluate("el => el.click()")
                    
                    download = await download_info.value
                    temp_path = await download.path()
                    if temp_path:
                        with open(temp_path, "rb") as f:
                            return f.read()
                    return None
                else:
                    logger.warning("⚠️ Could not find <i>download</i> button. Trying aria-label fallback...")
                    fallback_dl = page.locator("button[aria-label*='Download']").last
                    if await fallback_dl.count() > 0:
                        async with page.expect_download() as download_info:
                            await fallback_dl.evaluate("el => el.click()")
                        download = await download_info.value
                        temp_path = await download.path()
                        if temp_path:
                            with open(temp_path, "rb") as f:
                                return f.read()
                        return None
                    
                    logger.warning("⚠️ No download button found. Final fallback: img src")
                    src = await last_img.get_attribute("src")
                    resp = await page.request.get(src)
                    return await resp.body()
            else:
                raise RuntimeError("No images found after generation")

        finally:
            # We don't auto-close anymore to allow the caller to decide (especially for reuse)
            pass

    async def generate_batch(
        self,
        prompts: list[str],
        is_shorts: bool = False,
        style_suffix: str = "",
        delay_seconds: int = 5,
        character_paths: list[Path] = [],
        style_image_path: Optional[Path] = None
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

                        character_paths=character_paths if i == 0 else [], # Upload ONCE per session
                        style_image_path=style_image_path if i == 0 else None
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
