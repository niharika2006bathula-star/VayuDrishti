import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1536, "height": 1024})
        
        await page.goto('http://localhost:5173')
        await asyncio.sleep(4)
        
        # Take a screenshot of the "Now" step
        await page.screenshot(path='C:/Users/NIHARIKA/.gemini/antigravity-ide/brain/d0a20575-5482-4435-b3a6-4b7013deb152/hotspots_now.png')
        print("Now screenshot saved")
        
        # Click +24h
        await page.click('text="+24h"')
        await asyncio.sleep(2)
        await page.screenshot(path='C:/Users/NIHARIKA/.gemini/antigravity-ide/brain/d0a20575-5482-4435-b3a6-4b7013deb152/hotspots_24h.png')
        print("+24h screenshot saved")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
