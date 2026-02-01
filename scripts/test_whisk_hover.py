import asyncio
import os
import sys
from pathlib import Path

# Force UTF-8 encoding for Windows terminal
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from packages.services.whisk_agent import WhiskAgent

async def test_hover():
    # Use a dummy image for testing if possible, or just check visibility
    dummy_image = Path("whisk_full_page.png") # Use existing screenshot as a test image
    if not dummy_image.exists():
        open(dummy_image, "w").close()

    agent = WhiskAgent(headless=False)
    browser = None
    try:
        browser, pw = await agent.get_context()
        page = await browser.new_page()
        print("Navigating to Whisk Project...")
        await page.goto("https://labs.google/fx/tools/whisk/project", timeout=60000)
        
        # 1. Open Sidebar ASAP (Goal: Within 3s)
        print("Checking sidebar (Immediate Fast-Path)...")
        sidebar_trigger = page.get_by_text("ADD IMAGES")
        try:
            await sidebar_trigger.wait_for(state="attached", timeout=3000)
            await sidebar_trigger.first.click(force=True)
            print("SUCCESS: Clicked ADD IMAGES within 3s of load.")
            await asyncio.sleep(0.8)
        except Exception:
            print("Sidebar trigger not found immediately. Checking if already open...")
        
        # 2. Target Subject section
        print("Looking for Subject section...")
        subject_header = page.locator("h4, div").filter(has_text="Subject").first
        if await subject_header.count() > 0:
            print("Found Subject header.")
            
            # 2.5 Check Add Button
            add_btn = page.locator("div").filter(has=page.locator("h4", has_text="Subject")).locator("button[aria-label='Add new category'], button:has(i:text('control_point'))").first
            if await add_btn.count() > 0:
                print("SUCCESS: Found 'Add new category' button in Subject section.")
            else:
                print("FAILED: 'Add new category' button NOT found in Subject section.")

            # Find subject slots with person icon
            slots = page.locator("div:has(i:text('person'))").filter(has_not=page.locator("h1, h2, h3, h4"))
            count = await slots.count()
            print(f"Found {count} subject slots.")
            
            if count > 0:
                target_slot = slots.first
                await target_slot.scroll_into_view_if_needed()
                
                # Check for hidden input
                hidden_input = target_slot.locator("input[type='file']")
                if await hidden_input.count() > 0:
                    print("SUCCESS: Found hidden file input in slot.")
                    # Try setting it
                    await hidden_input.first.set_input_files(dummy_image)
                    print("Direct file set triggered.")
                
                # Check for upload button via hover
                print("Testing hover-reveal...")
                box = await target_slot.bounding_box()
                if box:
                    await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height'] * 0.8)
                    await asyncio.sleep(2)
                    
                    upload_btn = page.locator("button:has-text('Upload Image')").first
                    if await upload_btn.is_visible():
                        print("SUCCESS: Upload Image button is VISIBLE after hover.")
                    else:
                        print("Upload button not visible after hover.")
            else:
                print("No slots found.")
        else:
            print("Subject header not found.")

    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        if browser:
            await asyncio.sleep(5)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_hover())


if __name__ == "__main__":
    asyncio.run(test_hover())
