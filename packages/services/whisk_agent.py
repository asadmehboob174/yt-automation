
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
    # Global Lock to prevent concurrent browser launches (Playwright persistent profile restriction)
    _lock = asyncio.Lock()
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.profile_path = PROFILE_PATH
        self.profile_path.mkdir(parents=True, exist_ok=True)
        self.browser = None
        self.pw = None
        self.page = None
        self.gen_count = 0
        self.refresh_threshold = 1000  # DISABLED: Only refresh on explicit error, not proactively.
        logger.info("🦄 WhiskAgent initialized (Sequence Flow v3.3 - No Auto-Refresh)")
        
    async def _clean_stale_locks(self):
        """Removes Singleton lock files and kills dangling chrome processes."""
        
        # Windows-specific process cleanup
        if os.name == 'nt':
            try:
                # Force kill any dangling chrome/chromium processes to free the profile lock
                # Use /T to kill child processes (like the renderer) too
                os.system('taskkill /F /IM chrome.exe /T 2>nul')
                os.system('taskkill /F /IM chromium.exe /T 2>nul')
                logger.info("🔪 Force killed dangling browser processes on Windows.")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"⚠️ Failed to kill processes: {e}")

        locks = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
        for lock in locks:
            lock_path = self.profile_path / lock
            if lock_path.exists():
                try:
                    lock_path.unlink()
                    logger.info(f"🧹 Removed stale lock: {lock}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not remove lock {lock}: {e}")

    async def get_context(self) -> tuple[BrowserContext, any]:
        """Launch browser with persistent profile and retry logic for lock handling."""
        async with self._lock:
            playwright = await async_playwright().start()
            
            args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--start-maximized',
            ]
            
            MAX_RETRIES = 5
            for attempt in range(MAX_RETRIES):
                try:
                    browser = await playwright.chromium.launch_persistent_context(
                        user_data_dir=str(self.profile_path),
                        headless=self.headless,
                        args=args,
                        viewport=None, 
                    )
                    return browser, playwright
                except Exception as e:
                    error_msg = str(e).lower()
                    if "target page, context or browser has been closed" in error_msg or "existing browser session" in error_msg or "in use" in error_msg:
                        logger.warning(f"⚠️ Browser Lock detected (Attempt {attempt+1}/{MAX_RETRIES}). Cleaning and retrying...")
                        
                        # Only cleanup on retry
                        await self._clean_stale_locks()
                        await asyncio.sleep(2 * (attempt + 1)) # Exponential backoff
                    else:
                        logger.error(f"❌ Unexpected browser launch error: {e}")
                        # Cleanup playwright if we fail
                        await playwright.stop()
                        raise e
            
            await playwright.stop()
            raise RuntimeError("Failed to launch browser after multiple cleanup attempts.")

    async def close(self):
        """Close browser and stop playwright."""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.pw:
            await self.pw.stop()
            self.pw = None
        self.page = None

    async def _handle_session_refresh(self, page: Page) -> bool:
        """Restarts the project state to clear memory leaks."""
        self.gen_count += 1
        
        if self.gen_count >= self.refresh_threshold:
            logger.info(f"♻️ Refresh Threshold ({self.refresh_threshold}) reached. Cleaning session...")
            
            # 1. Clear IndexedDB and LocalStorage (Whisk stores project state here)
            await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            
            # 2. Hard Reload the URL
            try:
                await page.goto("https://labs.google/fx/tools/whisk/project", wait_until="networkidle", timeout=60000)
            except:
                await page.reload()
            
            # 3. Reset counter
            self.gen_count = 0
            logger.info("🚀 Session refreshed. Memory cleared.")
            return True
        return False

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

    async def _dismiss_dialogs(self, page: Page):
        """Helper to clear stacked modals."""
        for attempt in range(4): # Increased attempts
            try:
                # 1. Common Action Buttons
                # Added 'Explore' based on typical "New Feature" dialogs
                dialog_btn = page.locator("button").filter(
                    has_text=re.compile(r"^(CONTINUE|NEXT|GOT IT|START CREATING|DONE|EXPLORE)$", re.I)
                ).first
                
                if await dialog_btn.count() > 0 and await dialog_btn.is_visible():
                    logger.info(f"👋 Found dialog button '{await dialog_btn.inner_text()}'. Clicking...")
                    await dialog_btn.click()
                    await asyncio.sleep(0.5)
                    continue 
                
                # 2. Explicit Close Icon (X)
                close_icon = page.locator("button[aria-label='Close'], button[aria-label='close']").first
                if await close_icon.count() > 0 and await close_icon.is_visible():
                     logger.info("👋 Found Close icon. Clicking...")
                     await close_icon.click()
                     await asyncio.sleep(0.5)
                     
                # 3. Escape Key (Universal closer)
                # Only on later attempts to avoid closing wanted things too early? 
                # Actually, safe to try if we are blocked.
                if attempt > 1:
                     await page.keyboard.press("Escape")
                     
            except Exception:
                pass

    async def generate_image(
        self, 
        prompt: str, 
        is_shorts: bool = False,
        style_suffix: str = "",
        page: Optional[Page] = None,
        character_paths: list[Path] = [],
        style_image_path: Optional[Path] = None,
        skip_setup: bool = False
    ) -> bytes:
        """
        Generate a single image.
        Accepts optional 'page' to reuse existing browser session (critical for bulk).
        skip_setup: If True, assumes URL loaded and characters uploaded (Batch Mode).
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
            
            # Only navigate if NOT skipping setup (or if page is blank)
            if not skip_setup or page.url == "about:blank":
                await page.goto("https://labs.google/fx/tools/whisk/project", timeout=60000)
        
        try:
            # Check for login requirement
            if "Sign in" in await page.title() or await page.locator("text='Sign in'").count() > 0:
                logger.error("🛑 Whisk requires login! Please run the login helper script first.")
                raise RuntimeError("Authentication required. Run 'python scripts/auth_whisk.py'")
            
            # 0. Handle Onboarding Dialogs (Loop to clear stacked modals)
            await self._dismiss_dialogs(page)

            if not skip_setup:
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
                # Use robust selector (placeholder OR aria-label OR generic)
                textarea = page.locator("textarea[placeholder*='Describe your idea'], textarea[aria-label*='Prompt'], textarea[aria-label*='Describe'], textarea").first
                try:
                    await textarea.wait_for(state="visible", timeout=30000)
                except TimeoutError:
                    logger.error("❌ Could not find Whisk prompt input.")
                    raise UIChangedError("Whisk UI not loaded.")

                # 2. Set Aspect Ratio (Do this ONCE during setup)
                # User requested: "when using Generating all image button it should set aspect ratio once"
                target_aspect = "Portrait" if is_shorts else "Landscape"
                logger.info(f"📐 Setting Aspect Ratio: {target_aspect}")
                
                # Check for "aspect_ratio" (material icon) or "format_shapes" or similar
                # Also check aria-label
                aspect_btn = page.locator("button").filter(has_text=re.compile(r"aspect_ratio|format_shapes", re.I)).first
                if await aspect_btn.count() == 0:
                     aspect_btn = page.locator("button[aria-label*='Aspect ratio'], button[aria-label*='Format']").first
                
                if await aspect_btn.count() > 0:
                    await aspect_btn.click()
                    await asyncio.sleep(0.5)
                    
                    # Robust selection for 9:16 (Shorts) vs 16:9 (Landscape)
                    if is_shorts:
                        # Try 9:16, Portrait, Vertical
                        option = page.locator("text=9:16").first
                        if await option.count() == 0:
                            option = page.locator("text=Portrait").first
                        if await option.count() == 0:
                            option = page.locator("text=Vertical").first
                    else:
                        # Try 16:9, Landscape, Horizontal
                        option = page.locator("text=16:9").first
                        if await option.count() == 0:
                            option = page.locator("text=Landscape").first
                        if await option.count() == 0:
                            option = page.locator("text=Horizontal").first
                    
                    if await option.count() > 0:
                         await option.click()
                         logger.info(f"✅ Selected {target_aspect}")
                    else:
                         logger.warning(f"⚠️ Could not find option for {target_aspect}")
                    
                    # Close menu
                    await page.mouse.click(10, 10) 
                    await asyncio.sleep(0.5)
                else:
                    logger.warning("⚠️ Aspect Ratio button not found!")

            # Ensure textarea is available for subsequent steps (even if we skipped setup)
            textarea = page.locator("textarea[placeholder*='Describe your idea']")
            
            # 1.4 Ensure Sidebar is open for any uploads
            # ... (Rest of sidebar logic) ...

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
            if character_paths and not skip_setup:
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
                    # User requested: "add little more wait for subject to uploading"
                    # Updated: Added 3 seconds to each tier (1img->5s, 2imgs->10s, 3imgs->13s)
                    count = len(character_paths)
                    if count == 1:
                        wait_time = 5
                    elif count == 2:
                        wait_time = 10
                    elif count == 3:
                        wait_time = 13
                    else:
                        wait_time = max(5, (count * 5)) # Fallback
                        
                    logger.info(f"⏳ Waiting {wait_time} seconds for Subject Analysis ({count} images)...")
                    await asyncio.sleep(wait_time)

                    # --- SEED LOCKING (User Request) ---
                    # Click unlock icon (lock_open_right) to lock seed for consistency
                    # Now doing this INSIDE Phase 2 (Sidebar Context) as requested
                    try:
                        # 1. Open Settings Panel (The lock is inside this menu)
                        settings_btn = page.locator("button:has(i:text('tune'))")
                        
                        # Verify we can interact with settings (sometimes sidebar covers it?)
                        # But Settings is usually top-right in the main area.
                        
                        if await settings_btn.count() > 0:
                            logger.info("⚙️ Opening Settings menu to LOCK SEED...")
                            await settings_btn.first.click()
                            await asyncio.sleep(0.2) # Wait for popover

                            # 2. Look for button with unlock icon (lock_open_right)
                            unlock_btn = page.locator("button:has(i:text('lock_open_right'))")
                            
                            if await unlock_btn.count() > 0 and await unlock_btn.is_visible():
                                logger.info("🔒 Found 'Unlocked' seed icon. Clicking to LOCK seed per user request...")
                                await unlock_btn.first.click()
                                await asyncio.sleep(0.2)
                                
                                # 3. Close Settings (Click tune again or click outside)
                                await settings_btn.first.click()
                                await asyncio.sleep(0.2)
                            else:
                                logger.info("ℹ️ Seed appears already locked or not found.")
                                await settings_btn.first.click()
                        else:
                            logger.warning("⚠️ Could not find Settings (tune) button.")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to lock seed: {e}")
                    # -----------------------------------

                    # Wait after seed locking before entering prompt (user request)
                    logger.info("⏳ Waiting 3 seconds after seed lock before prompt entry...")
                    await asyncio.sleep(3)

            # 2. Enter Prompt
            # CRITICAL FIX: Handle empty prompts properly to avoid just "," in input
            if prompt and style_suffix:
                full_prompt = f"{prompt}, {style_suffix}"
            elif prompt:
                full_prompt = prompt
            elif style_suffix:
                full_prompt = style_suffix
                logger.warning(f"⚠️ Prompt is empty! Using style_suffix only: {style_suffix[:50]}...")
            else:
                logger.error("❌ CRITICAL: Both prompt and style_suffix are empty!")
                full_prompt = "A beautiful scene"  # Emergency fallback
            full_prompt = full_prompt.strip()
            
            # Ensure textarea is ready (sometimes analysis locks it)
            # Use robust selector again to be safe
            textarea = page.locator("textarea[placeholder*='Describe your idea'], textarea[aria-label*='Prompt'], textarea[aria-label*='Describe'], textarea").first
            await textarea.wait_for(state="visible", timeout=30000)
            
            # Robust Click with Interception Handling
            # If a dialog (like "Credits") appears *after* our initial check, this catches it.
            for attempt in range(3):
                try:
                    await textarea.click(timeout=3000)
                    break # Success!
                except Exception as e:
                    logger.warning(f"⚠️ Textarea click intercepted (Attempt {attempt+1}): {e}")
                    
                    # Check specifically for the Credits/Flow dialog mentioned in logs
                    # "Use your credits across Whisk and now Flow..."
                    credits_dialog_text = page.locator("text='Use your credits'")
                    if await credits_dialog_text.count() > 0:
                        logger.info("👋 'Credits' dialog detected. Attempting to dismiss...")
                        # Try generic closers again
                        await self._dismiss_dialogs(page)
                    else:
                        # Try generic closers anyway
                        await self._dismiss_dialogs(page)
                        
                    await asyncio.sleep(1)
            else:
                 # Final attempt force click if loop exhausted
                 await textarea.click(force=True)
            
            # Clear previous text and enter new prompt instantly
            # Using fill() instead of type() as it clears and fills almost instantly,
            # avoiding slow character-by-character typing.
            
            # Clean unwanted text from input if present (Safety Net)
            full_prompt = full_prompt.replace("Text-to-Image Prompt:", "").strip()
            
            await textarea.fill(full_prompt)
            logger.info(f"📝 Filled prompt: {full_prompt[:60]}...")
            await asyncio.sleep(2)  # Increased wait for UI to register the text
                    
            # 3. Click Generate / Submit
            # CRITICAL FIX: Count images BEFORE generating to detect when NEW image arrives
            pre_gen_count = await page.locator("img").count()
            logger.info(f"📸 Pre-generation image count: {pre_gen_count}")
            
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
                # CRITICAL FIX: Use a flag to prevent double-clicking
                click_succeeded = False
                try:
                    await submit_btn.evaluate("el => el.click()")
                    logger.info("🚀 Clicked 'Submit' (via JS force-click)")
                    click_succeeded = True
                except Exception as e:
                    logger.warning(f"JS Click failed: {e}. Trying standard click...")
                
                # Only try fallback if JS click definitively failed
                if not click_succeeded:
                    try:
                        await submit_btn.click(force=True)
                        logger.info("🚀 Clicked 'Submit' (via standard force-click)")
                    except Exception as e2:
                        logger.error(f"Both click methods failed: {e2}")
                
                # CRITICAL: Debounce - wait to prevent accidental double-click
                await asyncio.sleep(1)
            
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

            # 3.5 Safety Check (User Request)
            # After clicking 'Generate', check for the 'Content Safety' popup
            # It usually appears quickly.
            try:
                safety_popup = page.locator("text=/policy|safety|guidelines/i")
                if await safety_popup.count() > 0:
                    logger.error("🚫 Safety Filter Triggered!")
                    # Click the 'Dismiss' or 'Close' button to unblock the UI
                    await page.locator("button:has-text('Dismiss'), button:has-text('Close')").first.click()
                    raise RuntimeError("Safety Filter Violation")
            except Exception as e:
                # If checking fails, just ignore, it likely doesn't exist
                if "Safety Filter" in str(e): raise e
                pass

            # 4. Wait for Generation
            logger.info("⏳ Waiting for image generation...")
            # CRITICAL FIX: Wait longer for the image to actually render (not just placeholder)
            # The gray placeholder boxes need time to load the actual generated image
            await asyncio.sleep(15)  # Increased from 12s to 15s
            
            # Additional wait: Check for loading spinners/indicators
            # Whisk shows a progress indicator while generating
            try:
                # Look for any loading indicators and wait for them to disappear
                loading_indicator = page.locator("div[role='progressbar'], .loading, [aria-busy='true']")
                if await loading_indicator.count() > 0:
                    logger.info("⏳ Generation in progress, waiting for completion...")
                    await loading_indicator.first.wait_for(state="hidden", timeout=30000)
                    await asyncio.sleep(3)  # Extra buffer after loading completes
            except Exception:
                # If no loading indicator found or timeout, continue
                pass 
            
            # 5. Download Strategy
            # The download button is in a floating overlay on the top-right of the image.
            # We must aggressively hover to reveal it.
            
            # CRITICAL FIX: The "Subject" images in the sidebar might be picked up if we just use .last
            # We must identify the MAIN generated image. 
            # Strategy: The main image will be significantly LARGER than any thumbnail.
            
            # CRITICAL FIX: Retry logic to wait for the main image to render large enough
            # Sometimes it takes a moment to snap into full size layout
            
            target_img = None
            max_area = 0
            
            # Increased wait time for slower generations (up to 30s)
            for attempt in range(15):
                logger.info(f"🔍 Scan Attempt {attempt+1}/15 for Main Image...")
                
                # Relaxed selector to include blob: and data: URLs
                images = page.locator("img") 
                count = await images.count()
                logger.info(f"📷 Found {count} total images on page (pre-gen was {pre_gen_count})")
                
                # CRITICAL FIX: Track the image that is:
                # 1. In the LAST row (highest Y position)
                # 2. Among equal Y positions, pick the rightmost (highest X)
                # 3. Has a VALID src attribute (not placeholder)
                # This ensures we get the most recently generated image
                best_img = None
                best_y = -1
                best_x = -1
                best_area = 0
                
                for i in range(count):
                    img = images.nth(i)
                    try:
                        # Filter out tiny icons immediately
                        if await img.get_attribute("width") == "24": continue 
                        
                        # CRITICAL FIX: Check if image has a valid src (not placeholder)
                        img_src = await img.get_attribute("src")
                        if not img_src:
                            logger.debug(f"   [Img {i}] No src - skipping placeholder")
                            continue
                        
                        # Only accept blob:, data:, or http(s) URLs as valid image sources
                        is_valid_src = img_src.startswith(("blob:", "data:", "http://", "https://"))
                        if not is_valid_src:
                            logger.debug(f"   [Img {i}] Invalid src: {img_src[:30]}... - skipping")
                            continue
                        
                        box = await img.bounding_box()
                        if box:
                             area = box['width'] * box['height']
                             x_coord = box['x']
                             y_coord = box['y']
                             
                             logger.debug(f"   [Img {i}] {int(box['width'])}x{int(box['height'])} @ ({int(x_coord)},{int(y_coord)}) Area={int(area)}")

                             # SPATIAL FILTER: Ignore Sidebar (Left < 300px) and Header (Top < 40px)
                             if x_coord < 300:
                                 logger.debug(f"   -> Ignored (Sidebar Item)")
                                 continue
                             if y_coord < 40:
                                 logger.debug(f"   -> Ignored (Header Item)")
                                 continue

                             # Threshold: 15,000 (relaxed for 9:16 and mobile views)
                             if area > 15000: 
                                 # CRITICAL FIX: Select the image in the LAST row (highest Y)
                                 # Among images in the same row (similar Y within 50px tolerance), pick rightmost (highest X)
                                 is_same_row = abs(y_coord - best_y) < 50
                                 
                                 if y_coord > best_y + 50:
                                     # This image is in a new row BELOW the current best - always prefer it
                                     best_y = y_coord
                                     best_x = x_coord
                                     best_area = area
                                     best_img = img
                                     logger.debug(f"   -> Selected (New lower row)")
                                 elif is_same_row and x_coord > best_x:
                                     # Same row but further right - prefer it (rightmost in row)
                                     best_x = x_coord
                                     best_area = area
                                     best_img = img
                                     logger.debug(f"   -> Selected (Rightmost in row)")
                                 elif best_img is None:
                                     # First valid candidate
                                     best_y = y_coord
                                     best_x = x_coord
                                     best_area = area
                                     best_img = img
                                     logger.debug(f"   -> Selected (First candidate)")
                    except:
                        continue
                
                if best_img:
                    target_img = best_img
                    max_area = best_area
                    logger.info(f"✅ Found Main Image. Area: {int(max_area)}px, Position: ({int(best_x)}, {int(best_y)})")
                    break
                else:
                    logger.warning("⚠️ No large images found yet. Waiting 2s...")
                    await asyncio.sleep(2)
            
            if target_img:
                logger.info(f"✅ LOCK ON: Main Image (Area: {int(max_area)}px). Processing download...")
                last_img = target_img # Use this as the target
                
                # 1. Trigger Hover: specific move to top-right corner where buttons live
                logger.info("🖱️ Move mouse to image top-right to reveal buttons...")
                box = await last_img.bounding_box()
                if box:
                    # Move to center first
                    await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    await asyncio.sleep(0.2)
                    # Move to top-right (where the toolbar usually is)
                    await page.mouse.move(box["x"] + box["width"] - 40, box["y"] + 40, steps=10)
                    await asyncio.sleep(0.5)
                else:
                    await last_img.hover()
                    await asyncio.sleep(0.5)

                # 2. Find Download Button
                # It usually has an icon named 'download' or 'file_download'
                # It is often a <button> containing an <i> or <svg>
                
                # Strategy: Look for button with specific icon text within the general area
                # We filter by visibility because the hover should make it visible
                download_btns = page.locator("button").filter(has=page.locator("i, span", has_text=re.compile(r"download|file_download|save_alt", re.I)))
                
                target_btn = None
                img_box = await last_img.bounding_box()
                
                # Iterate to find the one that is visible AND inside the main image area
                cnt = await download_btns.count()
                logger.debug(f"found {cnt} potential download buttons. Filtering by location...")
                
                for i in range(cnt):
                    btn = download_btns.nth(i)
                    if await btn.is_visible():
                        if img_box:
                            btn_box = await btn.bounding_box()
                            if btn_box:
                                # Check if button is roughly within the image (allow some margin for overlay)
                                # Button Center
                                bx = btn_box['x'] + btn_box['width']/2
                                by = btn_box['y'] + btn_box['height']/2
                                
                                # Image bounds
                                ix = img_box['x']
                                iy = img_box['y']
                                iw = img_box['width']
                                ih = img_box['height']
                                
                                if (bx >= ix and bx <= ix + iw) and (by >= iy and by <= iy + ih):
                                    target_btn = btn
                                    logger.info(f"✅ Found button inside main image at ({int(bx)}, {int(by)})")
                                    break
                                else:
                                    logger.debug(f"   -> Ignored button at ({int(bx)}, {int(by)}) - Outside Main Image")
                        else:
                             # Fallback if no box (shouldn't happen for main img)
                             target_btn = btn
                             break
                
                # Fallback: Try aria-label
                if not target_btn:
                     aria_btns = page.locator("button[aria-label*='Download']")
                     cnt_aria = await aria_btns.count()
                     for i in range(cnt_aria):
                        btn = aria_btns.nth(i)
                        if await btn.is_visible():
                             # Same spatial check
                             if img_box:
                                btn_box = await btn.bounding_box()
                                if btn_box:
                                    bx = btn_box['x'] + btn_box['width']/2
                                    by = btn_box['y'] + btn_box['height']/2
                                    if (bx >= img_box['x'] and bx <= img_box['x'] + img_box['width']):
                                        target_btn = btn
                                        break
                             else:
                                target_btn = btn
                                break

                if target_btn:
                    logger.info("💾 Found visible download button! Clicking...")
                    
                    # Robust Click Loop for Download
                    download_obj = None
                    for attempt in range(3):
                        try:
                            async with page.expect_download(timeout=30000) as download_info:
                                await target_btn.click(timeout=5000)
                            download_obj = await download_info.value
                            break
                        except Exception as e:
                            logger.warning(f"⚠️ Download click intercepted/failed (Attempt {attempt+1}): {e}")
                            await self._dismiss_dialogs(page)
                            await asyncio.sleep(1)
                            
                            if attempt == 2:
                                # Final desperate attempt with force
                                try:
                                    logger.info("🔥 Final Attempt: Force clicking download...")
                                    async with page.expect_download(timeout=30000) as download_info:
                                        await target_btn.click(force=True)
                                    download_obj = await download_info.value
                                except Exception:
                                    logger.error("❌ Force click failed.")
                    
                    if download_obj:
                        temp_path = await download_obj.path()
                        if temp_path:
                            with open(temp_path, "rb") as f:
                                return f.read()
                        return None
                    # If failed, fall through to blob logic below
                    
                else:
                    logger.warning("⚠️ No visible download button found inside main image area.")
                    # Final fallback: Download via src
                    import base64
                    logger.info("⬇️ Fallback: Downloading via IMG SRC (Blob Support)...")
                    src = await last_img.get_attribute("src")
                    
                    if src.startswith("blob:"):
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
                        return base64.b64decode(b64_data)
                    else:
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
            was_refreshed = False
            for i, prompt in enumerate(prompts):
                logger.info(f"🔄 Bulk Generation {i+1}/{len(prompts)}")
                
                # SANITIZATION: Strict "One Line = One Image" Rule
                # Replace any internal newlines with spaces to prevent job fragmentation
                clean_prompt = prompt.replace("\n", " ").replace("\r", " ").strip()
                
                # RETRY LOGIC for each prompt in batch
                MAX_RETRIES = 3
                success = False
                
                for attempt in range(MAX_RETRIES):
                    try:
                        logger.info(f"🔄 Generation Attempt {attempt+1}/{MAX_RETRIES} for prompt {i+1}...")
                        # Determine if we need to upload characters
                        # 1. First item (i==0)
                        # 2. First attempt of that item (attempt==0)
                        # 3. OR if we just refreshed the session (was_refreshed)
                        should_upload_chars = ((i == 0 or was_refreshed) and attempt == 0)

                        img_bytes = await self.generate_image(
                            clean_prompt, 
                            is_shorts, 
                            style_suffix, 
                            page=page, # Pass the existing page object # Upload ONCE per session
                            character_paths=character_paths if should_upload_chars else [], 
                            style_image_path=style_image_path if should_upload_chars else None
                        )

                        if img_bytes:
                            results.append(img_bytes)
                            success = True
                            
                            if should_upload_chars:
                                was_refreshed = False
                            
                            # Validated success
                            # Call the refresh watchdog after each generation
                            was_refreshed = await self._handle_session_refresh(page)
                            
                            # Wait between generations
                            logger.info(f"💤 Waiting {delay_seconds}s...")
                            await asyncio.sleep(delay_seconds)
                            err_count = 0 # Reset error count on success
                            break # Move to next prompt
                        else:
                            raise RuntimeError("Generated image bytes empty")
                            
                    except Exception as e:
                        logger.error(f"❌ Batch Item {i+1} Attempt {attempt+1} Failed: {e}")
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(5)
                        else:
                            logger.error(f"🛑 Failed to generate prompt {i+1} after {MAX_RETRIES} attempts.")
                
                if not success:
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


# ============================================
# CLI for Manual Testing and Setup
# ============================================
if __name__ == "__main__":
    import sys
    
    async def setup_profile():
        """Open browser for manual login to save session."""
        print("🚀 Opening Whisk browser for Google login...")
        print(f"📁 Profile will be saved to: {PROFILE_PATH}")
        print("\n" + "="*50)
        print("INSTRUCTIONS:")
        print("1. A browser window will open")
        print("2. Sign in with your Google account")
        print("3. Wait for Whisk to load fully")
        print("4. Once logged in, close the browser window")
        print("5. Your session will be saved for future automation")
        print("="*50 + "\n")
        
        agent = WhiskAgent(headless=False)
        browser, pw = await agent.get_context()
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        await page.goto("https://labs.google/fx/tools/whisk/project", wait_until="networkidle", timeout=60000)
        
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
        
        print("\n✅ Profile saved! You can now run Whisk automation without logging in again.")
    
    async def test_generation():
        """Test image generation with sample prompt."""
        if len(sys.argv) < 2:
            print("Usage: python whisk_agent.py --setup    (for first-time login)")
            print("       python whisk_agent.py <prompt>   (for test generation)")
            return
        
        prompt = " ".join(sys.argv[1:])
        print(f"🎨 Generating image with prompt: {prompt[:50]}...")
        
        agent = WhiskAgent(headless=False)
        try:
            img_bytes = await agent.generate_image(prompt, is_shorts=False, style_suffix="")
            if img_bytes:
                output_path = Path("test_whisk_output.png")
                with open(output_path, "wb") as f:
                    f.write(img_bytes)
                print(f"✅ Generated: {output_path}")
            else:
                print("❌ Generation failed - no image bytes returned")
        finally:
            await agent.close()
    
    # Check for --setup flag
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        asyncio.run(setup_profile())
    else:
        asyncio.run(test_generation())

