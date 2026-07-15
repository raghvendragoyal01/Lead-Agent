import time
import random
import re
import csv
import os
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright

# ============================================================
# KEYWORDS & PATTERNS
# ============================================================
TECH_KEYWORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Angular", "Vue", "Svelte",
    "Node.js", "Express", "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Cassandra", "Elasticsearch",
    "Machine Learning", "Data Science", "Deep Learning", "TensorFlow", "PyTorch", 
    "DevOps", "CI/CD", "Jenkins", "Git", "Linux", "C++", "C#", ".NET", "Ruby", "Rails",
    "PHP", "Laravel", "Swift", "Kotlin", "Go", "Golang", "Rust", "Scala", "Spring", 
    "Django", "Flask", "FastAPI", "Hadoop", "Spark", "Kafka", "Tableau", "Power BI", 
    "Salesforce", "ServiceNow", "Cybersecurity", "Blockchain", "Web3", "HTML", "CSS"
]
VISA_KEYWORDS = ["H1B", "H-1B", "OPT", "CPT", "EAD", "Green Card", "US Citizen", "Citizen"]
US_STATES = "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming"
UNIVERSITY_PATTERNS = [
    rf"\b(?:University of (?:{US_STATES})|(?:{US_STATES}) State University|NYU|USC|ASU|MIT|Stanford|Harvard|Yale|Princeton|Cornell|Columbia|UCLA|UC Berkeley|Carnegie Mellon|Georgia Tech|Purdue|Boston University|Northeastern|Dartmouth|Brown|Duke|Northwestern|Johns Hopkins|Penn State|Ohio State)\b[^\n,;]{0,60}"
]

# ============================================================
# EXTRACTOR FUNCTIONS
# ============================================================
def extract_email(text):
    emails = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    valid = [e for e in emails if not re.search(r"\.(png|jpg|gif|css|js)$", e, re.IGNORECASE)]
    return valid[0] if valid else "N/A"

def extract_contact(text):
    phone = re.search(r"(?:\+91[\s\-]?)?[6-9]\d{9}|\+1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}", text)
    return phone.group().strip() if phone else "N/A"

def extract_technologies(text):
    found = [tech for tech in TECH_KEYWORDS if tech.lower() in text.lower()]
    return ", ".join(found) if found else "N/A"

def extract_visa(text):
    for visa in VISA_KEYWORDS:
        if visa.upper() in text.upper():
            return visa
    return "N/A"

def extract_year(text):
    years = re.findall(r"\b(20(?:1[5-9]|2[0-7]))\b", text)
    return sorted(set(years), reverse=True)[0] if years else "N/A"

def extract_university(text):
    indian_keywords = [
        "Delhi", "Mumbai", "Pune", "Anna", "Amity", "SRM", "VIT", "BITS", "IIT", "NIT", 
        "Manipal", "Thapar", "JNTU", "UPES", "KIIT", "Chandigarh", "Osmania", "Gujarat", 
        "Kerala", "Madras", "Kharagpur", "Kanpur", "Roorkee", "Guwahati", "Indore", 
        "Bangalore", "Hyderabad", "Noida", "Vellore", "Pilani", "Symbiosis", "NMIMS", 
        "Indraprastha", "Kurukshetra", "RGPV", "RTU", "VTU", "AKTU", "UPTU", "Jadavpur", 
        "Kalinga", "Sathyabama", "Banasthali", "Heriot", "Galgotias", "R.K PURAM", "Institute of Technology and Science",
        "India"
    ]
    us_acronyms = ["MIT", "USC", "ASU", "NYU", "UCLA", "CMU", "SUNY", "CUNY", "SJSU", "SDSU", "UMBC", "UMD", "UIUC", "UIC"]

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        has_uni_word = re.search(r"\b(University|College|Institute of Technology|Polytechnic|State)\b", line, re.IGNORECASE)
        has_acronym = any(re.search(rf"\b{acronym}\b", line) for acronym in us_acronyms)
        
        # If it looks like a university line and is a reasonable length
        if (has_uni_word or has_acronym) and 8 < len(line) < 120:
            is_indian = any(re.search(rf"\b{ind}\b", line, re.IGNORECASE) for ind in indian_keywords)
            if not is_indian:
                # Make sure it's not just a generic word like 'State' by itself
                if has_uni_word or has_acronym:
                    return line.replace(",", "").replace("\n", " ").strip()
                
    return "N/A"

def extract_name(url, page_text):
    match = re.search(r"linkedin\.com/in/([^/?#]+)", url)
    slug = match.group(1).replace("-", " ").title() if match else "Unknown"
    return slug

def extract_summary(page_text):
    """Grab a generic chunk of text near the top for a professional summary overview."""
    clean_text = re.sub(r'\s+', ' ', page_text).strip()
    return clean_text[:400] + "..." if len(clean_text) > 400 else clean_text

# ============================================================
# LINKEDIN NATIVE SEARCH & SCRAPE
# ============================================================
def human_delay(min_sec=3, max_sec=7):
    """Wait for a random amount of time to look human."""
    time.sleep(random.uniform(min_sec, max_sec))

def run_campaign(keyword_query, num_leads=5, output_file="campaign_results.csv"):
    print(f"\n========================================================")
    print(f"🚀 STARTING ADVANCED CAMPAIGN")
    print(f"🔍 Search Query : '{keyword_query}'")
    print(f"🎯 Target Leads : {num_leads} (Batch limit)")
    print(f"========================================================\n")

    user_data_dir = os.path.join(os.getcwd(), "linkedin_session")
    collected_urls = []
    seen_urls = set()

    # ----------------------------------------------------
    # 0. CROSS-RUN DEDUPLICATION
    # ----------------------------------------------------
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "linkedin_url" in row:
                        # Clean url to ensure standard format
                        clean = row["linkedin_url"].split("?")[0].rstrip("/")
                        seen_urls.add(clean)
            print(f"📦 Loaded {len(seen_urls)} previously scraped profiles to avoid duplicates.")
        except Exception as e:
            print(f"⚠️ Could not read previous results for deduplication: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,  
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = browser.new_page()

        # ----------------------------------------------------
        # 1. AUTHENTICATION CHECK
        # ----------------------------------------------------
        print("\nChecking login status...")
        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            human_delay()
            
            if "login" in page.url or "checkpoint" in page.url:
                print("\n⚠️ YOU ARE NOT LOGGED IN.")
                print("Please log in manually in the browser window that just opened.")
                print("You have 90 seconds to log in and pass any security checks...")
                time.sleep(90) 
                
                if "login" in page.url or "checkpoint" in page.url:
                     print("❌ Still not logged in. Exiting script. Please run it again and login.")
                     browser.close()
                     return
        except Exception as e:
            print(f"Error checking login status: {e}. Attempting to continue...")
            time.sleep(5) 

        # ----------------------------------------------------
        # 2. SEARCH AND COLLECT URLS
        # ----------------------------------------------------
        print("\n🔎 Initiating LinkedIn Native Search...")
        encoded_query = urllib.parse.quote(keyword_query)
        current_page = 1
        
        while len(collected_urls) < num_leads:
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}&page={current_page}"
            print(f"   -> Scraping search results page {current_page}...")
            
            try:
                page.goto(search_url, wait_until="domcontentloaded")
                human_delay(4, 7)
                
                # Scroll down slowly to load all results on the page
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 500);")
                    human_delay(1, 2)
                
                links = page.locator('a[href*="/in/"]').all()
                found_on_page = 0
                
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        clean_url = href.split("?")[0].rstrip("/")
                        if "linkedin.com" not in clean_url:
                            clean_url = "https://www.linkedin.com" + clean_url
                            
                        # DEDUPLICATION CHECK HERE
                        if clean_url not in collected_urls and clean_url not in seen_urls and len(collected_urls) < num_leads:
                            collected_urls.append(clean_url)
                            found_on_page += 1

                print(f"      Found {found_on_page} NEW profiles on this page. (Total Queue: {len(collected_urls)}/{num_leads})")

                if found_on_page == 0:
                    # To look human, if we find nothing, just wait a bit and move on
                    human_delay(3, 6)
                    # We might have hit the end, but let's try one more page just in case
                    if current_page > 10:
                        print("   ⚠️ Not finding new profiles. Stopping search phase to avoid bans.")
                        break

                current_page += 1
                
            except Exception as e:
                print(f"   ❌ Error during search: {e}")
                break

        print(f"\n✅ Finished searching. Proceeding to extract {len(collected_urls)} profiles.")

        # ----------------------------------------------------
        # 3. SCRAPE PROFILES WITH STEALTH & FILTERING
        # ----------------------------------------------------
        print("\n🕵️‍♂️ Starting Profile Data Extraction...")
        all_candidates = []
        file_exists = os.path.exists(output_file)
        fieldnames = ["name", "summary", "contact", "email", "technology", "visa", "year", "university", "linkedin_url", "scraped_at"]

        # Write header if new file
        if not file_exists:
            try:
                with open(output_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
            except PermissionError:
                print(f"❌ FATAL ERROR: Please close '{output_file}' in Excel or your text editor before running!")
                browser.close()
                return

        for i, url in enumerate(collected_urls, 1):
            print(f"\n[{i}/{len(collected_urls)}] Extracting: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded")
                
                # --- STEALTH SCROLLING (Human-like behavior) ---
                human_delay(2, 4)
                for _ in range(2):
                    page.evaluate("window.scrollBy(0, document.body.scrollHeight/4);")
                    time.sleep(random.uniform(0.5, 1.5)) # Micro-stutter
                    page.evaluate("window.scrollBy(0, -150);") # Scroll back up slightly
                    human_delay(1, 3)
                
                page.evaluate("window.scrollTo(0, document.body.scrollHeight/1.5);")
                human_delay(2, 4)

                # --- FETCH CONTACT INFO MODAL (EMAILS) ---
                contact_info_text = ""
                try:
                    # Find and click "Contact info" link
                    contact_link = page.locator("a#top-card-text-details-contact-info")
                    if contact_link.count() > 0:
                        contact_link.click()
                        time.sleep(2)
                        
                        # Extract text from the modal dialog
                        dialog = page.locator("div[role='dialog']")
                        if dialog.count() > 0:
                            contact_info_text = dialog.inner_text()
                            
                        # Close the modal safely
                        close_btn = page.locator("button[aria-label='Dismiss']")
                        if close_btn.count() > 0:
                            close_btn.click()
                            time.sleep(1)
                except Exception as e:
                    pass # Ignore and continue if modal fails

                # Extract all text from the page and combine with contact modal text
                page_text = page.inner_text("body") + " \n " + contact_info_text

                # --- REQUIREMENT FILTERING ---
                university = extract_university(page_text)
                technology = extract_technologies(page_text)

                if university == "N/A":
                    print(f"   ⏭️ SKIPPING: Failed requirements check (No valid US University found).")
                else:
                    candidate = {
                        "name": extract_name(url, page_text),
                        "summary": extract_summary(page_text),
                        "contact": extract_contact(page_text),
                        "email": extract_email(page_text),
                        "technology": technology,
                        "visa": extract_visa(page_text),
                        "year": extract_year(page_text),
                        "university": university,
                        "linkedin_url": url,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    all_candidates.append(candidate)
                    
                    try:
                        # Open, write, and close instantly to avoid lock errors
                        with open(output_file, "a", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writerow(candidate)
                        print(f"   -> SAVED: {candidate['name']} | Tech: {candidate['technology']} | Uni: {candidate['university']}")
                    except PermissionError:
                        print(f"   ❌ Could not save {candidate['name']}! Please close '{output_file}' in Excel immediately!")

            except Exception as e:
                print(f"   ❌ Error scraping profile: {e}")

                # --- DECOY ACTION / JITTER DELAY ---
                delay = random.uniform(12, 22)
                
                # 10% chance to go back to the feed and "browse" for a bit to reset bot patterns
                if random.random() < 0.10:
                    print(f"   🛡️ Anti-Ban triggered: Taking a short break in the LinkedIn feed...")
                    try:
                        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                        human_delay(10, 20)
                    except:
                        pass

                print(f"   ⏳ Safe delay: waiting {delay:.1f}s before next profile...")
                time.sleep(delay)

        browser.close()

    print(f"\n🎉 Campaign Complete! Successfully verified and saved {len(all_candidates)} new leads.")

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    SEARCH_QUERY = '("MS Graduate" OR "Master\'s Graduate") AND ("Open to Work" OR "OPT") AND ("United States" OR "USA")'
    # Keeping default to 35 so you can run it 4 times a day safely (~140/day)
    LEAD_COUNT = 35  
    
    run_campaign(keyword_query=SEARCH_QUERY, num_leads=LEAD_COUNT)
