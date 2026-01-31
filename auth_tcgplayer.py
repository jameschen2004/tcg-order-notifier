import os
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

def save_tcg_auth():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        print("opening TCGplayer login...")
        page.goto("https://sellerportal.tcgplayer.com/login")

        print("\n--- ACTION REQUIRED ---")
        print("1. Log in manually in the browser window.")
        print("2. Once you see your Dashboard/Home page.")
        input("3. Press ENTER to save your session.") 

        context.storage_state(path="tcg_state.json")
        print("\n'tcg_state.json' has been created with the correct credentials.")
        browser.close()

if __name__ == "__main__":
    save_tcg_auth()