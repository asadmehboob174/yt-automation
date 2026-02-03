
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
import json # Added for locator caching
import agentql # Added for Live Semantic Discovery
from pathlib import Path
from uuid import uuid4
from typing import Optional, Union, List

from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError
from dotenv import load_dotenv

load_dotenv() # Ensure AGENTQL_API_KEY is loaded

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
        self.locator_path = Path(__file__).parent / "whisk_locators.json"
        logger.info("🦄 WhiskAgent initialized (Hybrid Semantic Flow v4.0)")
        
    def _load_locators(self):
        """Load cached locators from JSON."""
        if self.locator_path.exists():
            try:
                with open(self.locator_path, "r") as f:
                    return json.load(f).get("locators", {})
            except:
                return {}
        return {}
        
    def _force_cleanup(self):
        """Removes lock files that might prevent Chrome from starting."""
        locks = [
            self.profile_path / "SingletonLock",
            self.profile_path / "SingletonCookie",
            self.profile_path / "SingletonSocket",
            self.profile_path / "lock",
            self.profile_path / "Default" / "Site Characteristics Database" / "LOCK",
            self.profile_path / "Default" / "Sync Data" / "LevelDB" / "LOCK"
        ]
        for lock in locks:
            if lock.exists():
                try:
                    lock.unlink()
                    logger.warning(f"🧹 Removed stale lock file: {lock}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to remove lock {lock}: {e}")

    async def get_context(self) -> tuple[BrowserContext, any]:
        """Launch browser with persistent profile and robustness retries."""
        # 1. Manually patch crash state to prevent "Restore pages" popup
        self._patch_profile()
        
        playwright = await async_playwright().start()
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-infobars',
            '--disable-session-crashed-bubble',
            '--disable-extensions',
            '--no-default-browser-check',
            '--no-first-run',
            '--disable-gpu',  # Added for stability
            '--ignore-certificate-errors',
            '--start-maximized'
        ]
        
        for attempt in range(3):
            try:
                browser = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_path),
                    channel="chrome",
                    headless=self.headless,
                    args=args,
                    viewport=None, # Use actual window size
                    no_viewport=True,
                    timeout=20000 # 20s timeout
                )
                return browser, playwright
            except Exception as e:
                logger.warning(f"⚠️ Browser launch failed (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    logger.info("♻️ Attempting profile cleanup and retry...")
                    self._force_cleanup()
                    await asyncio.sleep(2)
                else:
                    logger.error("❌ All browser launch attempts failed.")
                    raise e

    def _patch_profile(self):
        """Force-clears the Chrome 'Crashed' state in Preferences file."""
        for sub in ["Default", ""]:
            pref_path = self.profile_path / sub / "Preferences"
            if pref_path.exists():
                try:
                    with open(pref_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Ensure exit state is Normal
                    changed = False
                    if data.get("profile", {}).get("exit_type") != "Normal":
                        data.setdefault("profile", {})["exit_type"] = "Normal"
                        changed = True
                    if data.get("profile", {}).get("exited_cleanly") is not True:
                        data.setdefault("profile", {})["exited_cleanly"] = True
                        changed = True
                    
                    if changed:
                        with open(pref_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f)
                        logger.info(f"🧹 Patched Chrome Preferences at {pref_path}")
                except: pass

    async def _get_resilient_locator(self, page: Page, cached, key: str, fallback_selector: str, timeout_ms: int = 3000):
        """Tries cached locator for a few seconds, then falls back."""
        cached_selector = cached.get(key)
        if cached_selector:
            loc = page.locator(cached_selector)
            try:
                # Fast check for the cached one
                await loc.wait_for(state="attached", timeout=timeout_ms)
                logger.info(f"🎯 Resilient: Using cached '{key}'")
                return loc
            except:
                logger.warning(f"⚠️ Resilient: Cached '{key}' failed/timed out. Using fallback.")
        
        return page.locator(fallback_selector)

    async def _ensure_sidebar_open(self, page: Page):
        """Robustly opens the sidebar using Live AgentQL Queries."""
        # Verification: We look for the "Subject" header which only appears in the sidebar
        sidebar_marker = page.locator("h4, div").filter(has_text=re.compile(r"^Subject$", re.I)).first
        
        for attempt in range(5):
            try:
                # 1. Quick Visibility Check (STRICT POSITIONAL)
                if await sidebar_marker.is_visible(timeout=500):
                    box = await sidebar_marker.bounding_box()
                    # Sidebar is always on the left edge (X < 200)
                    if box and box['x'] >= 0 and box['x'] < 200:
                        logger.info(f"✅ Sidebar verified open (Header at X={box['x']})")
                        return True
            except: pass

            logger.info(f"📂 Sidebar NOT verified open (Attempt {attempt+1}/5). Trying trigger...")
            
            try:
                # 2. Live AgentQL Query (Async Safe)
                if os.getenv("AGENTQL_API_KEY"):
                    ql_page = await agentql.wrap_async(page) # Use wrap_async for Playwright Async
                    query = """
                    {
                        add_images_button {
                            xpath
                        }
                    }
                    """
                    response = await ql_page.query_elements(query)
                    
                    if response.add_images_button:
                        btn = response.add_images_button
                        logger.info("🤖 AgentQL found sidebar trigger. Clicking...")
                        try:
                            await btn.click(force=True, timeout=2000)
                            await asyncio.sleep(2)
                        except: pass
                        
                        # Verify immediately
                        if await sidebar_marker.is_visible(timeout=1000):
                            return True
                else:
                    logger.warning("No AGENTQL_API_KEY - skipping AI discovery.")
            except Exception as ql_err:
                logger.debug(f"AgentQL attempt failed: {ql_err}")

            # 3. Emergency Backup Strategies
            # Target the specific yellow button or the text
            fallbacks = [
                page.locator("button, div").filter(has_text=re.compile(r"ADD IMAGES", re.I)).last,
                page.locator("i:text('chevron_right')").locator("xpath=.."),
                page.locator("button").filter(has=page.locator("i:text('chevron_right')"))
            ]
            
            for f in fallbacks:
                try:
                    if await f.count() > 0:
                        btn = f.first
                        await btn.scroll_into_view_if_needed()
                        await btn.click(force=True, timeout=2000)
                        await asyncio.sleep(2)
                        if await sidebar_marker.is_visible(timeout=1000):
                            return True
                except: continue

            await asyncio.sleep(1)

        return False

    async def close(self):
        """Close browser and stop playwright."""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.pw:
                await self.pw.stop()
                self.pw = None
        except:
             logger.debug("Browser already closed.")
        finally:
            self.page = None
            self.browser = None
            self.pw = None

    async def _get_section_elements(self, page: Page, section_name: str, selector: str) -> list[object]:
        """Finds elements (inputs/buttons) strictly between section headers (v7.0 DOM-Sandwich)."""
        try:
            result = await page.evaluate('''(args) => {
                const { sectionName, elementSelector } = args;
                // 1. Identify only MAJOR Reference Headers (v7.0 Refinement)
                const candidates = Array.from(document.querySelectorAll("h1, h2, h3, h4, i, span, div, b, button"));
                const headers = candidates.filter(el => {
                    const text = (el.textContent || "").trim().toUpperCase();
                    // MUST be a major section title (SUBJECT, SCENE, STYLE, BACKGROUND)
                    const isMajorText = text === "SUBJECT" || text === "STYLE" || text === "SCENE" || text === "BACKGROUND" ||
                                        text === "SUBJECT REFERENCE" || text === "STYLE REFERENCE";
                    return isMajorText;
                });

                // 2. Sort headers and filter duplicates
                headers.sort((a, b) => a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);
                
                const uniqueHeaders = [];
                headers.forEach(h => {
                    const rect = h.getBoundingClientRect();
                    const last = uniqueHeaders[uniqueHeaders.length - 1];
                    if (!last || Math.abs(rect.top - last.getBoundingClientRect().top) > 5) {
                        uniqueHeaders.push(h);
                    }
                });

                const headerTexts = uniqueHeaders.map(h => (h.textContent || "").trim());

                // 3. Find our target header
                const targetHeader = uniqueHeaders.find(h => {
                    const text = (h.textContent || "").trim().toUpperCase();
                    if (sectionName === "STYLE") return text.includes("STYLE");
                    if (sectionName === "SUBJECT") return text.includes("SUBJECT");
                    if (sectionName === "SCENE" || sectionName === "BACKGROUND") return text.includes("SCENE") || text.includes("BACKGROUND");
                    return text.includes(sectionName);
                });

                if (!targetHeader) {
                    return { indices: [], headerTexts, targetHeaderText: null, nextHeaderText: null };
                }

                // 4. Find the next major header to create the "Sandwich"
                const nextHeader = uniqueHeaders[uniqueHeaders.indexOf(targetHeader) + 1];

                // 5. Select all elements matching selector in the entire document
                const allElements = Array.from(document.querySelectorAll(elementSelector));

                // 6. Filter elements that are strictly BETWEEN targetHeader and nextHeader
                const indices = [];
                allElements.forEach((el, idx) => {
                    const follows = targetHeader.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING;
                    const precedes = !nextHeader || (el.compareDocumentPosition(nextHeader) & Node.DOCUMENT_POSITION_FOLLOWING);
                    if (follows && precedes) indices.push(idx);
                });
                
                return { 
                    indices, 
                    headerTexts, 
                    targetHeaderText: (targetHeader.textContent || "").trim(),
                    nextHeaderText: nextHeader ? (nextHeader.textContent || "").trim() : null 
                };
            }''', { sectionName: section_name.toUpperCase(), elementSelector: selector })
            
            header_texts = result.get("headerTexts", [])
            target_header = result.get("targetHeaderText")
            next_header = result.get("nextHeaderText")
            indices = result.get("indices", [])
            
            logger.info(f"[Sandwich] {section_name}/{selector} | Headers: {header_texts} | Target: {target_header} | Next: {next_header} | Matches: {len(indices)}")
            
            if not indices:
                return []
                
            all_elements = await page.query_selector_all(selector)
            return [all_elements[i] for i in indices if i < len(all_elements)]
            
        except Exception as e:
            logger.debug(f"DOM-Sandwich Search failed for {section_name}/{selector}: {e}")
            return []
    async def _find_input_for_section(self, page: Page, section_name: str) -> Optional[object]:
        """Finds a file input by anchoring on a unique icon or text within a section (v7.0)."""
        elements = await self._get_section_elements(page, section_name, "input[type='file']")
        return elements[0] if elements else None

    async def generate_image(

        self, 
        prompt: str, 
        is_shorts: bool = False,
        style_suffix: str = "",
        page: Optional[Page] = None,
        character_paths: list[Path] = [],
        style_image_path: Optional[Path] = None,
        dry_run: bool = False
    ) -> bytes:
        """
        Generate a single image.
        Accepts optional 'page' to reuse existing browser session (critical for bulk).
        """
        logger.info(f"🎨 Whisk generation started. Style: {style_image_path}, Subjects: {len(character_paths)}")
        for i, p in enumerate(character_paths):
            exists = p.exists() if hasattr(p, 'exists') else False
            logger.info(f"  Subject {i+1}: {p} (Exists: {exists})")
        
        if style_image_path:
            exists = style_image_path.exists() if hasattr(style_image_path, 'exists') else False
            logger.info(f"  Style: {style_image_path} (Exists: {exists})")

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
        
        # 0. Load Cached Locators
        cached = self._load_locators()
        logger.info(f"📍 Loaded {len(cached)} cached locators.")
        
        try:
            # Check for login requirement
            if "Sign in" in await page.title() or await page.locator("text='Sign in'").count() > 0:
                logger.error("🛑 Whisk requires login! Please run the login helper script first.")
                raise RuntimeError("Authentication required. Run 'python scripts/auth_whisk.py'")

            # Cleanup any blocking popups (e.g. Restore pages, cookies)
            try:
                # Look for "Restore" or "Close" on modals
                restore_btn = page.locator("button").filter(has_text=re.compile(r"Restore", re.I))
                if await restore_btn.count() > 0 and await restore_btn.first.is_visible():
                    logger.info("🧹 Cleaning up 'Restore pages' popup...")
                    await restore_btn.first.click(force=True)
                    await asyncio.sleep(1)
            except: pass

            # 1. Ensure Sidebar is open for any uploads (BLOCKING)
            if style_image_path or character_paths:
                sidebar_ok = await self._ensure_sidebar_open(page)
                if not sidebar_ok:
                    logger.error("🛑 Sidebar failed to open! Aborting generation to prevent mis-typing.")
                    raise UIChangedError("Sidebar failed to open. Check 'ADD IMAGES' button.")
            else:
                logger.info("ℹ️ Text-only mode detected (Master Cast). Skipping sidebar opening.")

            # 1. Wait for the main interface (textarea)
            textarea_selector = "textarea[placeholder*='Describe your idea']"
            
            # EMERGENCY: One last check for the Restore popup which blocks the textarea
            try:
                restore_btn = page.locator("button").filter(has_text=re.compile(r"Restore", re.I))
                if await restore_btn.count() > 0 and await restore_btn.first.is_visible():
                    logger.info("🧹 Pre-type Cleanup: Clicking 'Restore'...")
                    await restore_btn.first.click(force=True)
                    await asyncio.sleep(1)
            except: pass

            textarea = await self._get_resilient_locator(
                page, cached, "prompt_textarea", textarea_selector
            )
            
            try:
                await textarea.wait_for(state="visible", timeout=30000)
            except TimeoutError:
                # If sidebar is open, Whisk might be shifted. Try a generic selector.
                textarea = page.locator("textarea").last
                await textarea.wait_for(state="visible", timeout=5000)

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

            # 2. Set Aspect Ratio

            # 1.5 Upload Style Image (PHASE 1)
            if style_image_path:
                exists = style_image_path.exists() if hasattr(style_image_path, "exists") else False
                if not exists:
                    logger.error(f"❗ CRITICAL: Style image file MISSING: {style_image_path}.")
                
                if (style_image_path and exists):
                    logger.info(f"🚀 PHASE 1: Style Upload. Path: {style_image_path}")
                    try:
                        # Identify Sidebar for scoping
                        sidebar = page.locator(".prebs, aside, [class*='sidebar'], [style*='overflow-y']").first
                        
                        # 1. DEFENSIVE SCROLL (Multi-strategy)
                        uploaded = False
                        scroll_selectors = ['aside', '[class*="sidebar"]', '.prebs', '[style*=' + "'overflow-y'" + ']']
                        
                        for scroll_pos in [0, 500, 1000, 1800]: # Brute force scan
                            logger.info(f"Scanning sidebar for 'Style' (Scroll: {scroll_pos})...")
                            try:
                                await page.evaluate(f"""(pos, selectors) => {{
                                    for (const sel of selectors) {{
                                        const el = document.querySelector(sel);
                                        if (el && (el.scrollHeight > el.clientHeight)) {{
                                            el.scrollTop = pos; return;
                                        }}
                                    }}
                                }}""", scroll_pos, scroll_selectors)
                            except: pass
                            await asyncio.sleep(1)

                            # 2. SURGICAL JS DISCOVERY (v7.0 DOM-Sandwich)
                            js_inputs = await self._get_section_elements(page, "STYLE", "input[type='file']")
                            if js_inputs:
                                logger.info("✅ DOM-Sandwich found Style input. Injecting...")
                                await js_inputs[0].set_input_files(style_image_path)
                                uploaded = True
                                break
                        
                        # 3. SCOPED LOCATOR (Secondary Fallback)
                        if not uploaded:
                            logger.info("Sandwich discovery missed. Trying scoped locator within Style section...")
                            style_header = page.locator("h1, h2, h3, h4, span, i").filter(has_text=re.compile(r"Style|stylus_note", re.I)).last
                            style_area = page.locator("div").filter(has=style_header).last
                            style_input = style_area.locator("input[type='file']")
                            if await style_input.count() > 0:
                                await style_input.first.set_input_files(style_image_path)
                                uploaded = True
                                logger.info("✅ Scoped locator found Style input.")

                        # 4. AGENTQL FALLBACK (Tertiary)
                        if not uploaded:
                            logger.info("Scoped locators missed. Trying AgentQL with sidebar focus...")
                            try:
                                ql_page = await agentql.wrap_async(page)
                                query = "{ sidebar { style_section { upload_box } } }"
                                response = await ql_page.query_elements(query)
                                if response.sidebar.style_section.upload_box:
                                    async with page.expect_file_chooser(timeout=10000) as fc_info:
                                        await response.sidebar.style_section.upload_box.click(force=True)
                                    await (await fc_info.value).set_input_files(style_image_path)
                                    uploaded = True
                            except: pass

                        if not uploaded:
                            logger.error("❌ CRITICAL: All Style upload methods failed.")
                            raise UIChangedError("Could not locate Style upload slot.")
                        
                        logger.info("✅ SUCCESS: Phase 1 (Style) complete. Waiting for analysis...")
                        await asyncio.sleep(10)
                            
                    except Exception as e:
                        logger.error(f"❌ ERROR in Style Upload Phase: {e}")
                        await asyncio.sleep(5)
                else:
                    logger.warning(f"⚠️ Skipping Phase 1: Style file missing/invalid.")
            else:
                logger.info("ℹ️ Skipping Phase 1: No style_image_path provided for this scene.")

            # 3. Handle Character Consistency (PHASE 2 - DOM-Sandwich Slotting)
            if character_paths:
                logger.info(f"🚀 PHASE 2: Subject Image Uploads. Count: {len(character_paths)}")
                try:
                    for i, char_path in enumerate(character_paths):
                        # RE-SCAN: Find all file inputs strictly inside the Subject sandwich
                        inputs = await self._get_section_elements(page, "SUBJECT", "input[type='file']")
                        count = len(inputs)
                        logger.info(f"Subject sandwich has {count} inputs. Need index {i}.")

                        # Add new slot if needed
                        if i >= count:
                            logger.info(f"Adding new Subject slot (slot {i+1})...")
                            # Find add button inside Subject sandwich
                            add_btns = await self._get_section_elements(page, "SUBJECT", "button[aria-label='Add new category'], button:has(i:text('control_point'))")
                            if not add_btns:
                                # Generic fallback if sandwich button fails
                                add_btn = page.locator("button[aria-label='Add new category'], button:has(i:text('control_point'))").first
                                await add_btn.click()
                            else:
                                await add_btns[0].click()
                            
                            await asyncio.sleep(4) # Allow UI to settle
                            inputs = await self._get_section_elements(page, "SUBJECT", "input[type='file']")
                            count = len(inputs)

                        if i < count:
                            logger.info(f"Uploading Character {i+1} to Subject sandwich input {i}...")
                            await inputs[i].set_input_files(char_path)
                            await asyncio.sleep(2)
                        else:
                            logger.error(f"❌ Failed to find/create Subject slot for character {i+1}")
                    
                    logger.info("⏳ Waiting 10 seconds for character analysis...")
                    await asyncio.sleep(10)
                except Exception as e:
                    logger.error(f"❌ Error in Subject Upload Phase: {e}")



            # 2. Enter Prompt (Clean up commas)
            full_prompt = f"{prompt.strip().rstrip(',')}, {style_suffix.strip().lstrip(',')}".strip().strip(",")
            
            # Ensure textarea is ready (sometimes analysis locks it)
            await textarea.wait_for(state="visible", timeout=10000)
            await textarea.click()
            
            # Clear previous text and entry
            await textarea.fill(full_prompt)
            await asyncio.sleep(0.5)


            
            # 3. Click Generate / Submit
            if dry_run:
                logger.info("🛑 DRY RUN: Skipping Generate click.")
                return b"dry_run_bytes"

            # Wait a moment for validation/UI to update after typing
            await asyncio.sleep(2)
            
            # Strategy A: Live AgentQL Query (Direct and Robust)
            submit_btn = None
            is_ql_submit = False
            try:
                ql_page = await agentql.wrap_async(page)
                # Query for generate_button directly to get interactable element
                query = "{ generate_button }"
                response = await ql_page.query_elements(query)
                if response.generate_button:
                    submit_btn = response.generate_button
                    is_ql_submit = True
                    logger.info("🤖 AgentQL found Generate button.")
            except Exception as ql_err:
                logger.debug(f"AgentQL submit detection failed: {ql_err}")

            # Strategy B: Whisk-Native Fallbacks
            if not is_ql_submit:
                 if not submit_btn or await submit_btn.count() == 0:
                    fallbacks = [
                        # The circular arrow button next to the prompt
                        page.locator("button:has(i)").filter(has_text="arrow_forward"),
                        # Or any button with a right arrow icon
                        page.locator("button").filter(has=page.locator("i, svg").filter(has_text=re.compile(r"arrow|send|forward", re.I))),
                        # Last resort: ARIA label
                        page.locator("button[aria-label*='Generate'], button[aria-label*='Submit']")
                    ]
                    for f in fallbacks:
                        if await f.count() > 0:
                            submit_btn = f.first
                            break

            if submit_btn:
                # Type check: AgentQL nodes don't have .count()
                if not is_ql_submit:
                    if await submit_btn.count() == 0:
                         logger.error("❌ Failed to find submit button via fallbacks.")
                         raise UIChangedError("Submit button missing.")
                    submit_btn = submit_btn.first 
                    logger.info(f"Found 'Submit' button ('{await submit_btn.inner_text()}'). Checking state...")

                # Force Click using JavaScript (Bypasses overlays/hit-tests)
                try:
                    if is_ql_submit:
                        await submit_btn.click(force=True)
                    else:
                        await submit_btn.evaluate("el => el.click()")
                    logger.info("🚀 Clicked 'Generate'")
                except Exception as e:
                     logger.warning(f"Click failed: {e}. Trying standard click...")
                     await submit_btn.click(force=True)
            
            else:
                logger.warning("⚠️ Specific 'arrow_forward' button not found. Trying generics...")
                # Strategy C: The Big Arrow Button is usually the last button with an SVG or Icon in the main area
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
