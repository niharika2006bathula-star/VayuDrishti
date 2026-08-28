import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        logs = []
        
        # Listen for console events
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
        # Listen for uncaught exceptions
        page.on("pageerror", lambda err: logs.append(f"[error] {err.message}"))
        
        try:
            await page.goto('http://localhost:5173')
            await asyncio.sleep(2)
            await page.wait_for_selector('text="Wazirpur"', timeout=5000)
            await page.click('text="Wazirpur"')
            
            # Wait for modal and click Nearby Sources
            await page.wait_for_selector('text="Nearby Sources"', timeout=8000)
            await page.click('text="Nearby Sources"')
            await asyncio.sleep(2)
            
            with open('C:/Users/NIHARIKA/.gemini/antigravity-ide/brain/d0a20575-5482-4435-b3a6-4b7013deb152/console_logs.txt', 'w') as f:
                if not logs:
                    f.write("No console logs or errors captured (Clean!)\n")
                else:
                    for log in logs:
                        f.write(log + '\n')
            print("Console logs captured successfully.")
            
        except Exception as e:
            print("Test failed:", e)

        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
