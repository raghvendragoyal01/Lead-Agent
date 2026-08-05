import sys
import os
import json
import time
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ACCOUNTS_JSON_PATH = "accounts.json"

def get_li_at_cookie(browser):
    """Retrieves the li_at session cookie directly from the browser context cookies list."""
    try:
        cookies = browser.cookies()
        for c in cookies:
            if c.get("name") == "li_at" and c.get("value"):
                return c.get("value")
    except Exception as e:
        print(f"   ⚠️ Error fetching cookies: {e}")
    return None

def setup_account_sessions():
    if os.path.exists(ACCOUNTS_JSON_PATH):
        with open(ACCOUNTS_JSON_PATH, "r", encoding="utf-8") as f:
            accounts = json.load(f)
    else:
        accounts = [
            {"id": "Account 1", "username": "", "password": "", "session_dir": "linkedin_session_1", "li_at": ""},
            {"id": "Account 2", "username": "", "password": "", "session_dir": "linkedin_session_2", "li_at": ""},
            {"id": "Account 3", "username": "", "password": "", "session_dir": "linkedin_session_3", "li_at": ""}
        ]

    print("\n========================================================")
    print("🔑 LINKEDIN INTERACTIVE LOGIN & SESSION CAPTURE TOOL")
    print("========================================================\n")
    print(f"Loaded {len(accounts)} accounts from '{ACCOUNTS_JSON_PATH}'.")

    with sync_playwright() as p:
        for idx, acc in enumerate(accounts, 1):
            acc_id = acc.get("id", f"Account {idx}")
            session_dir_name = acc.get("session_dir", f"linkedin_session_{idx}")
            session_dir = os.path.join(os.getcwd(), session_dir_name)
            username = acc.get("username", "").strip()
            password = acc.get("password", "").strip()

            # Skip accounts that already have valid li_at captured unless user wants to re-log
            if acc.get("li_at"):
                print(f"\n✅ Account [{idx}/{len(accounts)}]: '{acc_id}' already has a valid session ID saved. Skipping login.")
                continue

            print(f"\n--------------------------------------------------------")
            print(f"👉 Processing Account [{idx}/{len(accounts)}]: '{acc_id}'")
            print(f"   Session Folder: {session_dir_name}")
            print(f"--------------------------------------------------------")

            try:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=session_dir,
                    headless=False,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = browser.new_page()

                page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
                time.sleep(2)

                if username and password:
                    print(f"   🔑 Filling credentials for '{acc_id}'...")
                    try:
                        page.fill("input#username", username)
                        time.sleep(0.5)
                        page.fill("input#password", password)
                        time.sleep(0.5)
                        page.click("button[type='submit']")
                    except Exception as fill_err:
                        print(f"   Notice: Could not auto-fill fields: {fill_err}")

                print(f"\n⏳ PLEASE LOG IN NOW for '{acc_id}' in the browser window.")
                print("   Press ENTER in this terminal when you have finished logging in!")
                input(f"   >>> [Press ENTER when logged into {acc_id}] <<< ")

                time.sleep(1)
                extracted_li_at = get_li_at_cookie(browser)

                if extracted_li_at:
                    acc["li_at"] = extracted_li_at
                    print(f"✅ SUCCESSFULLY CAPTURED 'li_at' cookie for '{acc_id}': {extracted_li_at[:18]}...")
                else:
                    print(f"⚠️ Could not find 'li_at' cookie for '{acc_id}'. Make sure you are completely logged into the feed.")

                with open(ACCOUNTS_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(accounts, f, indent=2)
                print(f"💾 Saved session to {ACCOUNTS_JSON_PATH}")

                browser.close()
                time.sleep(1)

            except Exception as acc_err:
                print(f"❌ Error processing '{acc_id}': {acc_err}")

    print("\n========================================================")
    print("🎉 ALL DONE! Check accounts.json for your saved session tokens.")
    print("========================================================\n")

if __name__ == "__main__":
    setup_account_sessions()
