import asyncio
import os
import sys

# Ensure backend imports work
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from linkedin_scraper import BrowserManager, wait_for_manual_login

async def create_session():
    # Use headless=False so you can see the browser and solve the CAPTCHA/login manually
    async with BrowserManager(headless=False) as browser:
        print("Navigating to LinkedIn...")
        await browser.page.goto("https://www.linkedin.com/login")
        
        print("\n" + "="*60)
        print("PLEASE LOG IN TO LINKEDIN IN THE OPENED BROWSER WINDOW.")
        print("If asked, solve the CAPTCHA or 'Get App' screen.")
        print("Waiting up to 5 minutes...")
        print("="*60 + "\n")
        
        try:
            await wait_for_manual_login(browser.page, timeout=300)
            
            # Save session to root of project
            session_path = os.path.join(os.path.dirname(__file__), "..", "session.json")
            await browser.save_session(session_path)
            print(f"✓ Session successfully saved to {session_path}!")
            print("You can now use the TitanSwarm Auto-fill feature locally.")
        except Exception as e:
            print("\n❌ Login failed or timed out:", e)

if __name__ == "__main__":
    asyncio.run(create_session())
