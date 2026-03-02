import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The exact HTML from the user
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { background: #111; padding: 50px; }
        /* Dummy search bar to verify we don't click it */
        .search-container { margin-bottom: 20px; }
        input[type="search"] { padding: 10px; width: 300px; }
        
        /* The Actual Button HTML provided */
        #video-container { position: relative; width: 600px; height: 400px; background: #333; }
        .button-wrapper { position: absolute; bottom: 20px; right: 20px; }
    </style>
</head>
<body>
    <div class="search-container">
        <input type="search" placeholder="Search..." aria-label="Search">
        <button aria-label="Submit Search">🔍</button>
    </div>

    <div id="video-container">
        <!-- User's exact button HTML -->
        <div class="button-wrapper">
            <button data-slot="button" class="inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm leading-[normal] cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-60 disabled:cursor-not-allowed transition-colors duration-100 [&amp;_svg]:shrink-0 select-none border-border-l2 disabled:hover:bg-transparent h-10 px-4 py-2 rounded-full bg-[#000]/40 backdrop-blur-[2px] text-white hover:bg-[#000]/80 border-0 font-semibold hover:text-white" type="button" aria-label="Make video"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="stroke-[2] "><path fill-rule="evenodd" clip-rule="evenodd" d="M12 4C14.4853 4 16.5 6.01472 16.5 8.5V15.5C16.5 17.9853 14.4853 20 12 20H6C3.51472 20 1.5 17.9853 1.5 15.5V8.5C1.5 6.01472 3.51472 4 6 4H12Z" fill="currentColor"></path><path d="M22.5 19.0811L18.375 15.7812L18 15.4805V8.51953L18.375 8.21875L22.5 4.91895V19.0811Z" fill="currentColor"></path></svg>Make video</button>
        </div>
    </div>
    
    <div id="status" style="color: white; margin-top: 20px;">Watching for clicks...</div>
    
    <script>
        document.querySelector('button[aria-label="Make video"]').addEventListener('click', () => {
            document.getElementById('status').innerText = 'SUCCESS: Make Video Clicked!';
            document.getElementById('status').style.color = 'aqua';
            console.log("MAKE_VIDEO_CLICKED");
        });
        
        document.querySelector('button[aria-label="Submit Search"]').addEventListener('click', () => {
            document.getElementById('status').innerText = 'FAILED: Search Clicked!';
            document.getElementById('status').style.color = 'red';
            console.log("SEARCH_CLICKED");
        });
    </script>
</body>
</html>
"""

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Load the HTML
        await page.set_content(HTML_CONTENT)
        logger.info("Loaded test page.")
        
        # Wait a moment to simulate loading
        await asyncio.sleep(2)
        
        # ── The extraction logic from grok_agent.py ──
        logger.info("🎬 Waiting up to 15s for 'Make video' button...")
        make_video_clicked = False
        
        # Trying the exact selector first based on the HTML provided
        make_video_selectors = [
            "button[aria-label='Make video']",
            "button:has-text('Make video'):not([aria-label='Search'])",
            "div[role='button']:has-text('Make video')"
        ]
        
        combined_selector = ", ".join(make_video_selectors)
        logger.info(f"Looking for: {combined_selector}")
        
        try:
            # 1. Wait for ANY matching selector
            btn = await page.wait_for_selector(combined_selector, state="visible", timeout=15000)
            if btn:
                try:
                    await btn.click(timeout=5000)
                    logger.info("✅ Clicked 'Make video' button via locator")
                    make_video_clicked = True
                except Exception as e:
                    logger.warning(f"Locator click failed, trying JS evaluation: {e}")
                    
            # 2. JS Evaluation Fallback (bypasses Playwright interception checks)
            if not make_video_clicked:
                clicked = await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button, [role="button"], a, div'));
                    for (const b of btns) {
                        if (b.innerText && b.innerText.includes('Make video')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                if clicked:
                    logger.info("✅ Clicked 'Make video' button via JavaScript evaluation")
                    make_video_clicked = True
        except Exception as e:
            logger.warning(f"⚠️ 'Make video' button wait failed: {e}")
            
        # Verify result
        await asyncio.sleep(1)
        status_text = await page.locator('#status').inner_text()
        logger.info(f"Final Status: {status_text}")
        
        if "SUCCESS" in status_text:
            print("\n✅ TEST PASSED: Clicked the correct button!")
        else:
            print("\n❌ TEST FAILED: Clicked the wrong button or nothing!")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
