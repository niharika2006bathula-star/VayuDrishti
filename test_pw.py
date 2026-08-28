import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Test 1: Wazirpur
        await page.goto('http://localhost:5173')
        await asyncio.sleep(2)
        await page.wait_for_selector('text="Wazirpur"', timeout=5000)
        await page.click('text="Wazirpur"')
        
        # Wait for the modal and specifically the "Nearby Sources" tab to appear
        try:
            await page.wait_for_selector('text="Nearby Sources"', timeout=8000)
            await page.click('text="Nearby Sources"')
            await asyncio.sleep(2)
            
            modal = await page.query_selector('.max-w-2xl')
            if modal:
                await modal.screenshot(path='C:/Users/NIHARIKA/.gemini/antigravity-ide/brain/d0a20575-5482-4435-b3a6-4b7013deb152/wazirpur_modal.png')
                print("Wazirpur screenshot saved")
        except Exception as e:
            print("Wazirpur test failed:", e)
            
        # Test 2: Sirifort
        await page.goto('http://localhost:5173')
        await asyncio.sleep(2)
        await page.wait_for_selector('text="Sirifort"', timeout=5000)
        await page.click('text="Sirifort"')
        
        try:
            # Wait for modal to open
            await asyncio.sleep(3)
            # Take a screenshot to show the tab is NOT there
            modal = await page.query_selector('.max-w-2xl')
            if modal:
                await modal.screenshot(path='C:/Users/NIHARIKA/.gemini/antigravity-ide/brain/d0a20575-5482-4435-b3a6-4b7013deb152/sirifort_modal.png')
                print("Sirifort screenshot saved")
        except Exception as e:
            print("Sirifort test failed:", e)

        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
