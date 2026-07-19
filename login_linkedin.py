import os
from playwright.sync_api import sync_playwright

def login():
    user_data_dir = os.path.join(os.getcwd(), "linkedin_session")
    
    with sync_playwright() as p:
        print("🚀 Launching Chrome to authenticate LinkedIn...")
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            viewport={"width": 1280, "height": 800}
        )
        page = browser.new_page()
        page.goto("https://www.linkedin.com/login")
        
        print("\n========================================================")
        print("🚨 ACTION REQUIRED:")
        print("1. Please enter your email and password in the browser.")
        print("2. Solve any Captchas or 2FA if prompted.")
        print("3. Wait until you see your LinkedIn Home Feed.")
        print("4. Once you see your feed, you can close the browser window!")
        print("========================================================\n")
        
        # Wait indefinitely until the user closes the browser
        try:
            page.wait_for_timeout(99999999)
        except Exception:
            print("Browser closed! Your session cookies are now saved.")

if __name__ == "__main__":
    login()
