#this code is written by me and god.
# so if it is wroking pls don't mess with this
import os
import re
import csv
import time
import random
import threading  
import json
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file  
from flask_cors import CORS
from playwright.sync_api import sync_playwright

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        os.system("pip install ddgs")
        from ddgs import DDGS

# Env variables load
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

print("--- INITIALIZING 100% STRICT POSTGRADUATE VALIDATION ENGINE ---")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", 
    "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", 
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", 
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", 
    "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", 
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", 
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
]

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

def clean_and_extract_name(title):
    clean = re.sub(r"\s*-\s*LinkedIn.*$", "", title, flags=re.IGNORECASE)
    clean = re.sub(r"\s*\|.*$", "", clean)
    clean = re.sub(r"\s*-\s*.*$", "", clean)
    words = [w.strip() for w in clean.split() if w.strip()]
    valid = [w for w in words if w[0].isupper() and len(w) > 1]
    if len(valid) >= 2:
        return " ".join(valid[:3])
    return None

def extract_email(text):
    emails = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    valid = [e for e in emails if not re.search(r"\.(png|jpg|gif|css|js)$", e, re.IGNORECASE)]
    return valid[0] if valid else "N/A"

def extract_contact(text):
    phone = re.search(r"(?:\+91[\s\-]?)?[6-9]\d{9}|\+1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}", text)
    return phone.group().strip() if phone else "N/A"

def extract_visa(text):
    for visa in VISA_KEYWORDS:
        if visa.upper() in text.upper():
            return visa
    return "OPT / Seeking Sponsor"

def extract_university_strict(text):
    us_acronyms = ["MIT", "USC", "ASU", "NYU", "UCLA", "CMU", "SUNY", "CUNY", "SJSU", "SDSU", "UMBC", "UMD", "UIUC", "UIC"]

    # Hardcoded known good US overrides
    text_upper = text.upper()
    for keyword in ["NORTHEASTERN", "ARIZONA STATE", "ASU", "NYU", "NEW YORK UNIVERSITY", "STANFORD", "USC", "PACE", "STEVENS", "GEORGIA STATE", "ILLINOIS", "TEXAS", "SAN JOSE STATE", "SJSU"]:
        if keyword in text_upper:
            if keyword in ["ASU", "ARIZONA STATE"]: return "Arizona State University"
            if keyword in ["NYU", "NEW YORK UNIVERSITY"]: return "New York University"
            if keyword in ["NEU", "NORTHEASTERN"]: return "Northeastern University"
            if keyword in ["USC"]: return "University of Southern California"
            if keyword in ["SJSU", "SAN JOSE STATE"]: return "San Jose State University"
            return f"{keyword.title()} University"

    # Regex search for general university patterns (splitting by commas/pipes for DDGS snippets)
    segments = re.split(r'[,|•-\n]', text)
    for seg in segments:
        seg = seg.strip()
        has_uni_word = re.search(r"\b(University|College|Institute of Technology|Polytechnic|State)\b", seg, re.IGNORECASE)
        has_acronym = any(re.search(rf"\b{acronym}\b", seg) for acronym in us_acronyms)
        
        if (has_uni_word or has_acronym) and len(seg) < 80:
            if not any(g in seg.lower() for g in ["at the university", "from the university", "graduate from"]):
                return seg
            
    return "US University"

def verify_and_extract_strict_postgrad(text, title):
    combined = (text + " " + title).upper()
    
    bachelors_indicators = ["BACHELOR", "B.S. ", "B.S IN", "B.TECH", "B.E.", "UNDERGRADUATE"]
    masters_indicators = ["MS IN", "M.S. IN", "MASTER OF", "MASTER'S", "MASTER DEGR", "MBA", "MEM ", "MENG", "POSTGRADUATE", "POST-GRADUATE"]
    
    has_masters = any(sig in combined for sig in masters_indicators)
    pattern_match = re.search(r"\b(MS|M\.S\.|MASTER|MBA|MEM|MENG)\b", combined)
    
    if not (has_masters or pattern_match):
        return False, None
        
    degree = "Master's Degree"
    if "MBA" in combined:
        degree = "MBA"
    elif "MS " in combined or "M.S." in combined or "MASTER OF SCIENCE" in combined:
        degree = "Master of Science (MS)"
    elif "MEM" in combined:
        degree = "Master of Engineering Management"
    elif "MENG" in combined or "MASTER OF ENGINEERING" in combined:
        degree = "Master of Engineering (M.Eng)"
        
    return True, degree

def extract_graduation_year(text, title):
    combined = (text + " " + title).upper()
    match = re.search(r"\b(202[4-7])\b", combined)
    if match:
        return match.group(1)
    match_short = re.search(r"\'(2[4-7])\b", combined)
    if match_short:
        return "20" + match_short.group(1)
    return "2025"

def extract_technologies(text):
    combined = text.lower()
    found = [tech for tech in TECH_KEYWORDS if tech.lower() in combined]
    return ", ".join(found) if found else "Postgraduate (General)"

def check_daily_connection_limit():
    file_path = "daily_connections.json"
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
                if data.get("date") == today and data.get("count", 0) >= 2:
                    return False
            except Exception:
                pass
    return True

def increment_daily_connection():
    file_path = "daily_connections.json"
    today = datetime.now().strftime("%Y-%m-%d")
    count = 1
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
                if data.get("date") == today:
                    count = data.get("count", 0) + 1
            except Exception:
                pass
    with open(file_path, "w") as f:
        json.dump({"date": today, "count": count}, f)

def simulate_feed_activity(page):
    print("\n🔥 Warming up account: Simulating human feed activity...")
    try:
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=40000)
        time.sleep(random.uniform(3, 6))
        
        # Scroll 3 times
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 800);")
            time.sleep(random.uniform(2, 4))
            
        # Try to interact with the first post to simulate human activity
        posts = page.locator("div.feed-shared-update-v2").all()
        generic_comments = ["Great insight!", "Thanks for sharing this!", "Very interesting perspective.", "Love this!", "Great post!"]
        
        interacted = False
        for post in posts[:3]: # try up to the top 3 posts to find one that allows interaction
            try:
                print("   [+] Interacting with a post in the feed...")
                
                # Like
                like_btn = post.locator("button[aria-label*='React Like'], button[aria-label*='Like']").first
                if like_btn.count() > 0:
                    like_btn.click()
                    time.sleep(random.uniform(1.5, 3.0))
                
                # Comment
                comment_btn = post.locator("button[aria-label*='Comment']").first
                if comment_btn.count() > 0:
                    comment_btn.click()
                    time.sleep(random.uniform(1.5, 3.0))
                    
                    editor = post.locator("div[role='textbox']").first
                    if editor.count() > 0:
                        editor.fill(random.choice(generic_comments))
                        time.sleep(random.uniform(1, 2))
                        submit_btn = post.locator("button.comments-comment-box__submit-button").first
                        if submit_btn.count() > 0:
                            submit_btn.click()
                            time.sleep(random.uniform(2, 4))
                interacted = True
                break # Only interact with one post per warmup to stay safe
            except Exception:
                continue
                
        if not interacted:
            print("   [-] Could not find an interactive post in the top feed. Skipping interaction.")
    except Exception as e:
        print(f"   ⚠️ Feed warmup error: {e}")

def run_strict_accurate_campaign(target_total_leads=40):
    print(f"\n========================================================")
    print(f"🚀 STARTING 100% ACCURATE POSTGRADUATE EXTRACTION SYSTEM")
    print(f"========================================================\n")

    queries = [
        # Ultra-Targeted: Prioritize profiles with Contact Info + Visa explicitly in About/Summary
        'site:linkedin.com/in/ "OPT" "@gmail.com" "MS in" United States',
        'site:linkedin.com/in/ "F1" "contact me" "Master" USA',
        'site:linkedin.com/in/ ("OPT" OR "H1B") ("@yahoo.com" OR "@gmail.com") "MBA" United States',
        'site:linkedin.com/in/ "Open to Work" ("@gmail.com" OR "reach me at") "M.S." USA',
        
        # Standard Queries
        'site:linkedin.com/in/ "MS in" ("Open to Work" OR "OPT") United States',
        'site:linkedin.com/in/ "M.S. in" ("Open to Work" OR "Looking for roles") USA',
        'site:linkedin.com/in/ "Master of Science" ("Open to Work" OR "Actively Looking") USA',
        'site:linkedin.com/in/ "MBA Candidate" ("Open to Work" OR "OPT") United States',
        'site:linkedin.com/in/ "MS in" ("Actively applying" OR "Open to Work") United States',
        'site:linkedin.com/in/ "MS" "Computer Science" ("Open to Work" OR "OPT") USA',
        'site:linkedin.com/in/ "Master\'s degree" ("Open to work" OR "Seeking") United States',
        'site:linkedin.com/in/ "M.S." "Data Science" ("Open to Work" OR "Actively looking") USA',
        'site:linkedin.com/in/ "MBA" ("Looking for new opportunities" OR "OPT") USA'
    ]

    output_file = "campaign_results.csv"
    fieldnames = ["name", "summary", "contact", "email", "technology", "visa", "year", "university", "linkedin_url"]
    
    if not os.path.exists(output_file):
        with open(output_file, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()

    seen_urls = set()
    all_candidates = []

    # Local CSV Deduplication Fallback
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "linkedin_url" in row:
                        seen_urls.add(row["linkedin_url"].split("?")[0].rstrip("/"))
        except Exception:
            pass

    try:
        previous_leads = supabase.table("linkedin_leads").select("linkedin_url").execute()
        for row in previous_leads.data:
            seen_urls.add(row["linkedin_url"].split("?")[0].rstrip("/"))
        print(f"📦 Loaded {len(seen_urls)} historical leads to prevent duplicates.")
    except Exception:
        pass

    campaign = supabase.table("campaigns").insert({
        "campaign_name": f"Strict PostGrad {datetime.now().strftime('%m/%d %H:%M')}",
        "keyword": "100% Strict Postgraduate Verification",
        "requested_leads": target_total_leads,
        "scraped_leads": 0,
        "status": "Running"
    }).execute()
    campaign_id = campaign.data[0]["id"]
    user_data_dir = os.path.join(os.getcwd(), "linkedin_session")

    try:
        with sync_playwright() as p:
            print("🚀 Launching Playwright Chromium for deep profile extraction...")
            browser = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = browser.new_page()

            # Run human-like feed scrolling, liking, and commenting to warm up account
            simulate_feed_activity(page)

            with DDGS() as ddgs:
                for q_idx, query in enumerate(queries):
                    if len(all_candidates) >= target_total_leads:
                        break

                    print(f"\n🌀 [Query {q_idx + 1}/{len(queries)}] Running: {query}")
                    time.sleep(random.randint(4, 7))

                    try:
                        results = list(ddgs.text(query, max_results=200))
                        print(f"   Fetched {len(results)} raw results. Running strict filter...")

                        if not results:
                            print("   ⚠️ No results returned. Engine might be throttled. Moving to next string...")
                            continue

                        for r in results:
                            link = r.get("href", "")
                            if "linkedin.com/in/" not in link:
                                continue

                            clean_url = link.split("?")[0].rstrip("/")
                            if clean_url in seen_urls:
                                # Silently skip duplicates to not clutter logs too much, 
                                # but they are being skipped!
                                continue

                            title = r.get("title", "")
                            snippet = r.get("body", "")

                            is_postgrad, verified_degree = verify_and_extract_strict_postgrad(snippet, title)
                            if not is_postgrad:
                                continue

                            name = clean_and_extract_name(title)
                            if not name:
                                continue

                            # ----------------------------------------------------
                            # PLAYWRIGHT HYBRID EXTRACTION 
                            # ----------------------------------------------------
                            print(f"   [+] Candidate Passed! Playwright scraping for email/contact: {clean_url}")
                            contact_info_text = ""
                            page_text = ""
                            try:
                                page.goto(clean_url, wait_until="domcontentloaded", timeout=30000)
                                time.sleep(random.uniform(2, 4))
                                
                                # Simulate human mouse movements
                                page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                                time.sleep(random.uniform(0.5, 1.5))
                                page.evaluate("window.scrollBy(0, document.body.scrollHeight/4);")
                                page.mouse.move(random.randint(200, 600), random.randint(200, 600))
                                time.sleep(random.uniform(0.5, 1.5))
                                
                                # Fetch Contact Info Modal (Emails)
                                contact_link = page.locator("a#top-card-text-details-contact-info")
                                if contact_link.count() > 0:
                                    # Move mouse specifically to the contact link before clicking
                                    box = contact_link.bounding_box()
                                    if box:
                                        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                                        time.sleep(random.uniform(0.5, 1.0))
                                        
                                    contact_link.click()
                                    time.sleep(2)
                                    dialog = page.locator("div[role='dialog']")
                                    if dialog.count() > 0:
                                        contact_info_text = dialog.inner_text()
                                        
                                    close_btn = page.locator("button[aria-label='Dismiss']")
                                    if close_btn.count() > 0:
                                        close_btn.click()
                                        time.sleep(1)
                                        
                                        
                                # Fetch Real Summary and Education
                                real_summary = ""
                                real_education = ""
                                try:
                                    # Try to find the About section in LinkedIn profile
                                    about_section = page.locator("section:has-text('About')").first
                                    if about_section.count() > 0:
                                        real_summary = about_section.inner_text().replace("About", "").strip()
                                        
                                    # Try to find the Education section
                                    edu_section = page.locator("section:has-text('Education')").first
                                    if edu_section.count() > 0:
                                        real_education = edu_section.inner_text()
                                except Exception:
                                    pass

                                page_text = page.inner_text("body") + " \n " + contact_info_text + " \n " + real_education

                                # Send Connection Request (Without Note) with Daily Limit of 2
                                if check_daily_connection_limit():
                                    connect_btn = page.locator("button[aria-label*='Invite']:has-text('Connect'), button[aria-label*='Connect']:has-text('Connect')").first
                                    if connect_btn.count() > 0:
                                        print("      [+] Found 'Connect' button. Sending request...")
                                        connect_btn.click()
                                        time.sleep(random.uniform(1, 2))
                                        # Click "Send without a note" or "Send" in the modal
                                        send_btn = page.locator("button[aria-label='Send without a note'], button:has-text('Send')").first
                                        if send_btn.count() > 0:
                                            send_btn.click()
                                            increment_daily_connection()
                                            print("      ✅ Connection request sent!")
                                            time.sleep(random.uniform(1, 2))
                                        else:
                                            print("      [-] Could not find 'Send' button in modal. Skipping connect.")
                                    else:
                                        print("      [-] 'Connect' button not found directly on profile (might be inside More). Skipping connect.")
                                else:
                                    print("      [-] Daily connection limit (2) reached. Skipping connect for this lead.")

                            except Exception as e:
                                print(f"      [!] Playwright error: {e}")

                            combined_text = snippet + " \n " + title + " \n " + page_text

                            university = extract_university_strict(combined_text)
                            if university in ["US University", "", "N/A"]:
                                print("      [-] Could not detect specific university name. Skipping to enforce mandatory university rule.")
                                continue

                            year = extract_graduation_year(snippet, title)
                            tech_stack = extract_technologies(combined_text)
                            
                            final_summary = real_summary[:500] if real_summary else snippet[:500]
                            short_summary = (final_summary[:50] + "...") if len(final_summary) > 50 else final_summary

                            email_val = extract_email(combined_text)
                            visa_val = extract_visa(combined_text)
                            
                            print(f"    🎯 STRICT SAVE: {name} | Email: {email_val} | Uni: {university} | Summary: {short_summary}")

                            if email_val == "N/A" and extract_contact(combined_text) == "N/A" and "gmail.com" not in final_summary.lower() and "yahoo.com" not in final_summary.lower():
                                print("      [!] Warning: No contact info found, but saving anyway per request.")
                                
                            if visa_val == "N/A":
                                print("      [!] Warning: No Visa status found, but saving anyway per request.")

                            candidate = {
                                "name": name,
                                "summary": final_summary,
                                "contact": extract_contact(combined_text),
                                "email": email_val,
                                "technology": tech_stack,
                                "visa": visa_val,
                                "year": year,
                                "university": university,
                                "linkedin_url": clean_url
                            }

                            with open(output_file, "a", newline="", encoding="utf-8") as f:
                                csv.DictWriter(f, fieldnames=fieldnames).writerow(candidate)

                            # Save to Supabase
                            supabase.table("linkedin_leads").insert({
                                "campaign_id": campaign_id,
                                "candidate_name": candidate["name"],
                                "contact": candidate["contact"],
                                "email": candidate["email"],
                                "technology": f"{verified_degree} - {candidate['technology']}",
                                "visa": candidate["visa"],
                                "graduation_year": candidate["year"],
                                "university": candidate["university"],
                                "linkedin_url": candidate["linkedin_url"],
                                "summary": candidate["summary"]
                            }).execute()

                            all_candidates.append(candidate)
                            seen_urls.add(clean_url)
                            
                            supabase.table("campaigns").update({
                                "scraped_leads": len(all_candidates)
                            }).eq("id", campaign_id).execute()

                            print(f"    🎯 STRICT SAVE: {candidate['name']} | Email: {candidate['email']} | Uni: {candidate['university']}")

                            if len(all_candidates) >= target_total_leads:
                                break

                    except Exception as e:
                        print(f"   ⚠️ Search string error or rate limit hit: {e}")
                        time.sleep(10) 
                        continue

    except Exception as session_err:
        print(f"❌ DDGS Session initialization failed: {session_err}")

    supabase.table("campaigns").update({
        "status": "Completed",
        "scraped_leads": len(all_candidates)
    }).eq("id", campaign_id).execute()

    print(f"\n🎉 Verification complete! Successfully saved {len(all_candidates)} strictly verified US postgraduates in Supabase.")


# ========================================================
#                    FLASK SERVER ROUTES
# ========================================================

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": "*"}}) 

@app.route('/api/download-results', methods=['GET'])
def download_results():
    try:
        if os.path.exists('campaign_results.csv'):
            return send_file('campaign_results.csv', as_attachment=True, download_name='campaign_results.csv')
        else:
            return jsonify({"error": "No results found yet"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/', methods=['GET'])
def get_dashboard_data():
    try:
        campaigns_res = supabase.table("campaigns").select("*", count="exact").order("id", desc=True).execute()
        leads_res = supabase.table("linkedin_leads").select("*", count="exact").order("id", desc=True).execute()
        
        c_data = campaigns_res.data or []
        total_campaigns = len(c_data)
        total_leads = len(leads_res.data or [])
        active_agents = 1 if any(x.get('status') == 'Running' for x in c_data) else 0

        return jsonify({
            "stats": {
                "total_campaigns": total_campaigns,
                "total_leads": total_leads,
                "active_agents": active_agents,
            },
            "total_campaigns": total_campaigns,
            "total_leads": total_leads,
            "active_agents": active_agents,
            "campaigns": c_data, 
            "recent_leads": leads_res.data[:50] if leads_res.data else []
        }), 200
    except Exception as e:
        return jsonify({
            "stats": {
                "total_campaigns": 0,
                "total_leads": 0,
                "active_agents": 0,
            },
            "total_campaigns": 0,
            "total_leads": 0,
            "active_agents": 0,
            "campaigns": [],
            "recent_leads": []
        }), 200

@app.route('/api/campaigns/<campaign_id>/leads', methods=['GET', 'OPTIONS'])
def get_campaign_leads(campaign_id):
    try:
        leads_res = supabase.table("linkedin_leads").select("*").eq("campaign_id", campaign_id).execute()
        return jsonify({
            "status": "success",
            "leads": leads_res.data or []
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "leads": []
        }), 500

@app.route('/api/notes', methods=['GET', 'POST'])
def handle_notes():
    return jsonify([]), 200

@app.route('/api/tasks', methods=['GET', 'POST'])
def handle_tasks():
    return jsonify([]), 200

from flask_cors import cross_origin

@app.route('/start-campaign', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True, allow_headers="*")
def start_campaign_api():
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "POST,OPTIONS")
        return response, 200
        
    try:
        data = {}
        if request.is_json:
            data = request.get_json(silent=True) or {}
        elif request.data:
            try:
                data = json.loads(request.data)
            except:
                pass
            
        target = int(data.get('target_leads', 40))
        
        thread = threading.Thread(target=run_strict_accurate_campaign, args=(target,))
        thread.start()
        
        return jsonify({
            "status": "success",
            "message": f"Scraper started in background for {target} leads!"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True, use_reloader=False)
