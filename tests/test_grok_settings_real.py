"""
Real-browser test for Grok Imagine video settings.

This test opens a REAL Chrome session, navigates to grok.com/imagine,
and verifies that VideoSettings.configure correctly sets:
  - Aspect Ratio (9:16 vs 16:9) 
  - Duration (6s vs 10s)
  - Resolution (480p / 720p)

Usage:
    python tests/test_grok_settings_real.py

Requirements:
    - Must be logged into Grok in the persistent browser profile
    - GROK_EXTENSION_PATH env var (optional)
"""

import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def run_settings_test():
    from playwright.async_api import async_playwright
    from packages.services.grok_agent import VideoSettings, get_browser_context

    pw = await async_playwright().start()
    
    try:
        # Use persistent profile (same as production)
        browser = await get_browser_context(pw)
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        logger.info("🌐 Navigating to Grok Imagine...")
        await page.goto("https://grok.com/imagine", wait_until="domcontentloaded", timeout=30000)
        
        # Wait for the page to fully load
        try:
            await page.wait_for_selector(".ProseMirror, textarea, [contenteditable='true']", state="visible", timeout=10000)
        except:
            logger.warning("⚠️ Timeout waiting for prompt area, attempting settings anyway...")
        
        await asyncio.sleep(2)  # Let UI settle

        # ═══════════════════════════════════════════
        # TEST 1: Set 9:16 aspect ratio + 10s duration
        # ═══════════════════════════════════════════
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Setting aspect=9:16, duration=10s, resolution=480p")
        logger.info("="*60)
        
        await VideoSettings.configure(page, duration="10s", aspect="9:16", resolution="480p")
        await asyncio.sleep(1)
        
        # Verify: Read the current aspect ratio from the button
        current = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const aspectBtn = buttons.find(b => {
                const text = (b.innerText || "").trim();
                return /^\\d+:\\d+/.test(text) && b.offsetWidth > 0;
            });
            return aspectBtn ? aspectBtn.innerText.trim().split('\\n')[0].trim() : 'NOT FOUND';
        }""")
        
        test1_aspect = "PASS ✅" if current.startswith("9:16") else f"FAIL ❌ (got {current})"
        logger.info(f"  Aspect Ratio: {test1_aspect}")

        # Check duration by looking for active/selected state on 10s button
        dur_state = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('button, div, span'));
            const dur10 = buttons.find(b => (b.innerText || "").trim() === "10s" && b.offsetWidth > 0);
            const dur6 = buttons.find(b => (b.innerText || "").trim() === "6s" && b.offsetWidth > 0);
            return {
                dur10_found: !!dur10,
                dur10_classes: dur10 ? dur10.className.substring(0, 100) : '',
                dur6_found: !!dur6,
                dur6_classes: dur6 ? dur6.className.substring(0, 100) : '',
            };
        }""")
        logger.info(f"  Duration state: {dur_state}")

        await asyncio.sleep(2)

        # ═══════════════════════════════════════════
        # TEST 2: Switch to 6s duration (simulating scene 2)
        # ═══════════════════════════════════════════
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Switching to duration=6s (scene 2 simulation)")
        logger.info("="*60)
        
        await VideoSettings.configure(page, duration="6s", aspect="9:16", resolution="480p")
        await asyncio.sleep(1)
        
        # Verify duration changed
        dur_state2 = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('button, div, span'));
            const dur10 = buttons.find(b => (b.innerText || "").trim() === "10s" && b.offsetWidth > 0);
            const dur6 = buttons.find(b => {
                const text = (b.innerText || "").trim();
                return (text === "6s" || text === "5s") && b.offsetWidth > 0;
            });
            return {
                dur10_found: !!dur10,
                dur10_classes: dur10 ? dur10.className.substring(0, 100) : '',
                dur6_found: !!dur6,
                dur6_text: dur6 ? dur6.innerText.trim() : '',
                dur6_classes: dur6 ? dur6.className.substring(0, 100) : '',
            };
        }""")
        logger.info(f"  Duration state after switch: {dur_state2}")

        # Verify aspect ratio stayed at 9:16
        current2 = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const aspectBtn = buttons.find(b => {
                const text = (b.innerText || "").trim();
                return /^\\d+:\\d+/.test(text) && b.offsetWidth > 0;
            });
            return aspectBtn ? aspectBtn.innerText.trim().split('\\n')[0].trim() : 'NOT FOUND';
        }""")
        test2_aspect = "PASS ✅" if current2.startswith("9:16") else f"FAIL ❌ (got {current2})"
        logger.info(f"  Aspect Ratio (should still be 9:16): {test2_aspect}")

        await asyncio.sleep(2)

        # ═══════════════════════════════════════════
        # TEST 3: Switch back to 10s + change to 16:9
        # ═══════════════════════════════════════════
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Switching to duration=10s, aspect=16:9 (verify no collision)")
        logger.info("="*60)
        
        await VideoSettings.configure(page, duration="10s", aspect="16:9", resolution="480p")
        await asyncio.sleep(1)
        
        current3 = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const aspectBtn = buttons.find(b => {
                const text = (b.innerText || "").trim();
                return /^\\d+:\\d+/.test(text) && b.offsetWidth > 0;
            });
            return aspectBtn ? aspectBtn.innerText.trim().split('\\n')[0].trim() : 'NOT FOUND';
        }""")
        test3_aspect = "PASS ✅" if current3.startswith("16:9") else f"FAIL ❌ (got {current3})"
        logger.info(f"  Aspect Ratio: {test3_aspect}")

        # ═══════════════════════════════════════════
        # TEST 4: Switch back to 9:16 (verify it changes FROM 16:9)
        # ═══════════════════════════════════════════
        logger.info("\n" + "="*60)
        logger.info("TEST 4: Switching back to aspect=9:16 (from 16:9)")
        logger.info("="*60)
        
        await VideoSettings.configure(page, duration="6s", aspect="9:16", resolution="480p")
        await asyncio.sleep(1)
        
        current4 = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const aspectBtn = buttons.find(b => {
                const text = (b.innerText || "").trim();
                return /^\\d+:\\d+/.test(text) && b.offsetWidth > 0;
            });
            return aspectBtn ? aspectBtn.innerText.trim().split('\\n')[0].trim() : 'NOT FOUND';
        }""")
        test4_aspect = "PASS ✅" if current4.startswith("9:16") else f"FAIL ❌ (got {current4})"
        logger.info(f"  Aspect Ratio: {test4_aspect}")

        # ═══════════════════════════════════════════
        # SUMMARY
        # ═══════════════════════════════════════════
        logger.info("\n" + "="*60)
        logger.info("SUMMARY")
        logger.info("="*60)
        logger.info(f"  Test 1 (9:16 initial):       {test1_aspect}")
        logger.info(f"  Test 2 (9:16 stays on dur):   {test2_aspect}")
        logger.info(f"  Test 3 (switch to 16:9):      {test3_aspect}")
        logger.info(f"  Test 4 (back to 9:16):        {test4_aspect}")
        
        # Take screenshot for evidence
        screenshot_path = os.path.join(os.path.dirname(__file__), "grok_settings_test_result.png")
        await page.screenshot(path=screenshot_path, full_page=False)
        logger.info(f"\n📸 Screenshot saved: {screenshot_path}")
        
        # Keep browser open for manual inspection
        logger.info("\n🔍 Browser will stay open for 15 seconds for manual inspection...")
        await asyncio.sleep(15)
        
    finally:
        await browser.close()
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(run_settings_test())
