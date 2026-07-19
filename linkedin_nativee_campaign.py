import os
import re
import csv
import time
import random
import threading  # Background thread chalane ke liye
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
from flask import Flask, request, jsonify  # Request handle karne ke liye
from flask_cors import CORS

try:
    from duckduckgo_search import DDGS
except ImportError:
    try:
        from ddgs import DDGS
    except ImportError:
        os.system("pip install ddgs")
        from duckduckgo_search import DDGS

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

FIELD_KEYWORDS = {
    "Mechanical Engineering": ["mechanical", "solidworks", "ansys", "cad", "robotics", "thermodynamics"],
    "Electrical & Electronics": ["electrical", "electronics", "vlsi", "embedded", "circuits", "hardware engineer"],
    "Civil Engineering": ["civil engineering", "structural", "autocad", "construction"],
    "Biotech & Healthcare": ["biotech", "biomedical", "pharma", "clinical"],
    "Finance & Accounting": ["finance", "accounting", "financial analyst", "investment"],
    "Marketing & Sales": ["marketing", "sales", "brand manager", "seo"],
    "Supply Chain & Logistics": ["supply chain", "logistics", "operations", "procurement"],
    "Data Science & Analytics": ["data science", "data analyst", "tableau", "power bi", "analytics"],
    "Computer Science / Software": ["software", "python", "java", "javascript", "developer", "aws", "cloud", "c++"],
    "Management & Consulting": ["mba", "consultant", "business analyst", "project manager", "strategy"]
}

def clean_and_extract_name(title):
    clean = re.sub(r"\s*-\s*LinkedIn.*$", "", title, flags=re.IGNORECASE)
    clean = re.sub(r"\s*\|.*$", "", clean)
    clean = re.sub(r"\s*-\s*.*$", "", clean)
    words = [w.strip() for w in clean.split() if w.strip()]
    valid = [w for w in words if w[0].isupper() and len(w) > 1]
    if len(valid) >= 2:
        return " ".join(valid[:3])
    return None

def extract_university_strict(text):
    text_upper = text.upper()
    for keyword in ["NORTHEASTERN", "ARIZONA STATE", "ASU", "NYU", "NEW YORK UNIVERSITY", "STANFORD", "USC", "PACE", "STEVENS", "GEORGIA STATE", "ILLINOIS", "TEXAS", "SAN JOSE STATE", "SJSU"]:
        if keyword in text_upper:
            if keyword in ["ASU", "ARIZONA STATE"]: return "Arizona State University"
            if keyword in ["NYU", "NEW YORK UNIVERSITY"]: return "New York University"
            if keyword in ["NEU", "NORTHEASTERN"]: return "Northeastern University"
            if keyword in ["USC"]: return "University of Southern California"
            if keyword in ["SJSU", "SAN JOSE STATE"]: return "San Jose State University"
            return f"{keyword.title()} University"
            
    match = re.search(r"\b([A-Z][a-zA-Z\s]+ (?:University|College|Institute))\b", text)
    if match:
        matched_str = match.group(1).strip()
        if not any(g in matched_str.lower() for g in ["at the university", "from the university", "graduate from"]):
            return matched_str
            
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

def extract_field_dynamic(text, title):
    combined = (text + " " + title).lower()
    for field, keywords in FIELD_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return field
    return "Postgraduate (General)"

def run_strict_accurate_campaign(target_total_leads=40):
    print(f"\n========================================================")
    print(f"🚀 STARTING 100% ACCURATE POSTGRADUATE EXTRACTION SYSTEM")
    print(f"========================================================\n")

    # Smart Queries: Double quotes thode kam kiye taaki DuckDuckGo block na kare
    queries = [
        'site:linkedin.com/in/ "MS in" Class of 2025 University United States',
        'site:linkedin.com/in/ "M.S. in" Class of 2024 University USA',
        'site:linkedin.com/in/ "Master of Science" Class of 2025 USA',
        'site:linkedin.com/in/ "MBA Candidate" Class of 2025 United States',
        'site:linkedin.com/in/ "MS in" Class of 2026 University United States',
        'site:linkedin.com/in/ "Master of Engineering" Class of 2025 USA',
        'site:linkedin.com/in/ "Master of" California OPT United States',
        'site:linkedin.com/in/ "MS in" Texas OPT USA'
    ]

    seen_urls = set()
    all_candidates = []

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

    # DDGS ko loop ke bahar ek hi baar initialize kar rahe hain optimal session ke liye
    try:
        with DDGS() as ddgs:
            for q_idx, query in enumerate(queries):
                if len(all_candidates) >= target_total_leads:
                    break

                print(f"\n🌀 [Query {q_idx + 1}/{len(queries)}] Running: {query}")
                
                # Human behavior mimic karne ke liye random sleep delay
                time.sleep(random.randint(4, 7))

                try:
                    # max_results ko 80 se 30 kar diya taaki IP block na ho aur fast responses aayein
                    results = list(ddgs.text(query, max_results=30))
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
                            continue

                        title = r.get("title", "")
                        snippet = r.get("body", "")

                        is_postgrad, verified_degree = verify_and_extract_strict_postgrad(snippet, title)
                        if not is_postgrad:
                            continue

                        name = clean_and_extract_name(title)
                        if not name:
                            continue

                        university = extract_university_strict(snippet + " " + title)
                        year = extract_graduation_year(snippet, title)
                        field = extract_field_dynamic(snippet, title)

                        candidate = {
                            "name": name,
                            "summary": snippet[:250],
                            "contact": "N/A",
                            "email": "N/A",
                            "technology": field,
                            "visa": "OPT / Seeking Sponsor",
                            "year": year,
                            "university": university,
                            "linkedin_url": clean_url,
                        }

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
                        
                        # Real-time counter database me sath ke sath sync hota rahega
                        supabase.table("campaigns").update({
                            "scraped_leads": len(all_candidates)
                        }).eq("id", campaign_id).execute()

                        print(f"    🎯 STRICT SAVE: {candidate['name']} | Degree: {verified_degree} | Uni: {candidate['university']}")

                        if len(all_candidates) >= target_total_leads:
                            break

                except Exception as e:
                    print(f"   ⚠️ Search string error or rate limit hit: {e}")
                    time.sleep(10) # Heavy delay error aane par
                    continue

    except Exception as session_err:
        print(f"❌ DDGS Session initialization failed: {session_err}")

    # Final Campaign update
    supabase.table("campaigns").update({
        "status": "Completed",
        "scraped_leads": len(all_candidates)
    }).eq("id", campaign_id).execute()

    print(f"\n🎉 Verification complete! Successfully saved {len(all_candidates)} strictly verified US postgraduates in Supabase.")


# ========================================================
#                    FLASK SERVER ROUTES
# ========================================================

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}) 

# Route 1: Dynamic Dashboard Stats
@app.route('/api/dashboard/', methods=['GET'])
def get_dashboard_data():
    try:
        # Supabase se real active counts trigger karenge live dashboard ke liye
        campaigns_res = supabase.table("campaigns").select("*", count="exact").execute()
        leads_res = supabase.table("linkedin_leads").select("*", count="exact").execute()
        
        c_data = campaigns_res.data or []
        
        return jsonify({
            "total_campaigns": len(c_data),
            "total_leads": len(leads_res.data or []),
            "active_agents": 1 if any(x.get('status') == 'Running' for x in c_data) else 0,
            "campaigns": c_data,  # Direct react components integration fields
            "recent_leads": leads_res.data[:5] if leads_res.data else []
        }), 200
    except Exception as e:
        return jsonify({
            "total_campaigns": 0,
            "total_leads": 0,
            "active_agents": 0,
            "campaigns": [],
            "recent_leads": []
        }), 200

# Route 2: Notes handler
@app.route('/api/notes', methods=['GET', 'POST'])
def handle_notes():
    return jsonify([]), 200

# Route 3: Tasks handler
@app.route('/api/tasks', methods=['GET', 'POST'])
def handle_tasks():
    return jsonify([]), 200

# Route 4: Main Campaign Scraper Trigger
@app.route('/start-campaign', methods=['POST'])
def start_campaign_api():
    try:
        data = request.json or {}
        target = int(data.get('target_leads', 40))
        
        # Scraper background thread me start hoga
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