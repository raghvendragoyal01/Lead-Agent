# RGTVetrex — AI Lead Outbound Engine
### Product Overview & Technical Documentation

---

## What is this system?

Ek fully automated AI-powered outbound sales engine jo aapke liye automatically leads dhundta hai, qualify karta hai, personalized emails likhta hai, aur send karta hai — bina kisi manual kaam ke.

**Simple words mein:** Aap bas batao "mujhe Mumbai ke SaaS startups ke founders chahiye" — system baaki sab khud karta hai.

---

## Complete Pipeline Flow

```
Client gives Campaign Input
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 1 — INTELLIGENT SEARCH                        │
│  AI generates 5 targeted search queries              │
│  → Tinyfish Search API                               │
│  → DuckDuckGo fallback                               │
│  → Google Dorking (site:linkedin.com, filetype:pdf)  │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 2 — MULTI-SOURCE LEAD DISCOVERY               │
│  Source 1: Company Websites (official pages)         │
│  Source 2: LinkedIn X-Ray (via Google cache)         │
│  Source 3: Reddit (official API — PRAW)              │
│  Source 4: Quora (public answer pages)               │
│  Source 5: PDF Staff Directories                     │
│  Source 6: Instagram public bios                     │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 3 — UNIVERSAL ANTI-BOT SCRAPER (5 Tiers)     │
│                                                      │
│  Tier 1 → Tinyfish Fetch API (fastest)               │
│  Tier 2 → curl_cffi (TLS/JA3 fingerprint spoof)      │
│           mimics real Chrome at network level         │
│  Tier 3 → Camoufox (anti-detect Firefox browser)     │
│           beats Cloudflare, removes webdriver flag   │
│  Tier 4 → Playwright + Stealth patches               │
│           full JS rendering + Bézier mouse paths     │
│  Tier 5 → BeautifulSoup deep extraction (7 layers)   │
│                                                      │
│  + Session Cookie Cache (reuse verified sessions)    │
│  + Hidden JSON API Detection (10x faster when found) │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 4 — AI EXTRACTION                             │
│  Gemini/Llama reads scraped content                  │
│  Extracts: Name, Email, Phone, Title, Company        │
│  Fixes obfuscated emails: "name at domain dot com"   │
│  Validates email format                              │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 5 — DEDUPLICATION & VALIDATION               │
│  → Root domain dedup (same company = 1 lead)        │
│  → Email format validation                          │
│  → Neo4j graph database check (already contacted?)  │
│  → Best contact selection (named person > generic)  │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 6 — AI QUALIFIER                              │
│  LLM reviews and standardizes each lead             │
│  Confidence scoring (0.0 → 1.0)                     │
│  Drops only malformed/no-contact-info leads         │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 7 — HUMAN APPROVAL GATE  ← CLIENT REVIEWS    │
│  Dashboard shows all qualified leads                │
│  Client approves / rejects individual leads         │
│  AI pre-generates personalized email draft          │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 8 — PERSONALIZED EMAIL DRAFTING              │
│  Llama 70B writes hyper-personalized cold email     │
│  Uses company description for personalization       │
│  RAG system pulls successful past templates         │
│  Under 100 words, professional tone                 │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 9 — AUTOMATED EMAIL SENDING                  │
│  Sends via configured SMTP                          │
│  2-second rate limit between emails                 │
│  Logs every send to database                        │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 10 — REPLY MONITORING & FOLLOW-UPS           │
│  Monitors inbox for replies                         │
│  Auto-schedules follow-up sequences                 │
│  Tracks: sent / replied / bounced / positive        │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  STAGE 11 — DASHBOARD & ANALYTICS                   │
│  Live campaign status                               │
│  Lead growth charts                                 │
│  Industry distribution                              │
│  Success rate metrics                               │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | FastAPI (Python) | REST API, campaign management |
| Frontend | React + TypeScript + Vite | Dashboard UI |
| Primary LLM | NVIDIA Llama 3.1 70B | Extraction, drafting |
| Fallback LLMs | Groq, OpenRouter, Gemini 2.5 Flash | Reliability chain |
| Graph DB | Neo4j Aura | Lead memory, deduplication |
| Vector DB | Qdrant Cloud | Email template RAG |
| SQL DB | Supabase (PostgreSQL) | Users, campaigns, tasks, notes |
| Scraping Tier 1 | Tinyfish Fetch API | Cloud-based bypass scraper |
| Scraping Tier 2 | curl_cffi | TLS/JA3 fingerprint spoofing |
| Scraping Tier 3 | Camoufox | Anti-detect Firefox browser |
| Scraping Tier 4 | Playwright + Stealth | Headless Chromium + stealth patches |
| Scraping Tier 5 | BeautifulSoup (7-layer) | Static HTML deep extraction |
| Search | Tinyfish Search + DDG | URL discovery |
| Email | SMTP (Gmail) | Outbound email sending |

---

## Scraper — Full Technical Details

### 5-Tier Anti-Bot Strategy

#### Tier 1 — Tinyfish Fetch API
- Cloud-based fetcher with built-in bot bypass
- Returns clean markdown — no HTML parsing needed
- Fastest tier (~1-2 seconds per page)

#### Tier 2 — curl_cffi (TLS/JA3 Fingerprint Spoof)
- Python's default `requests` library has a unique TLS handshake that Cloudflare detects instantly
- `curl_cffi` compiles low-level curl code that sends Chrome 120/124/131 or Safari 17/18 TLS fingerprints
- Sites see a real browser at the TCP network level
- Bypasses ~60% of bot blocks without launching any browser
- Profiles rotated: `chrome120`, `chrome124`, `chrome131`, `safari17_0`, `safari18_0`

#### Tier 3 — Camoufox (Anti-Detect Firefox)
- Custom Firefox build with stealth patches at the engine level
- Removes automation indicators (`navigator.webdriver`, canvas fingerprint, WebGL leaks)
- Handles Cloudflare Turnstile and complex JS-rendered pages
- Best for Indian government/education websites

#### Tier 4 — Playwright + Stealth
- Full headless Chromium browser
- Stealth JS injected before every page load:
  - Removes `navigator.webdriver = true` flag
  - Fakes `navigator.plugins` (5 plugins)
  - Fakes `navigator.languages`
  - Adds `window.chrome` object
- **Bézier mouse paths** — curved organic mouse movement, not straight lines
- **Poisson-distributed delays** — random 1-7 second waits, not fixed `sleep(2)`
- Heavy assets (images, fonts, videos) blocked to save bandwidth

#### Tier 5 — BeautifulSoup 7-Layer Extraction
1. `mailto:` and `tel:` links → direct email/phone extraction
2. Meta tags (OG, Twitter Card, schema.org, author)
3. JSON-LD structured data (`<script type="application/ld+json">`)
4. Microdata (`itemprop` attributes — contact schemas)
5. HTML comments containing `@` or contact keywords
6. `<address>` HTML tags (spec-defined contact blocks)
7. Visible text keyword scan (email, phone, contact, director etc.)

### Session Cookie Cache
- After Camoufox/Playwright solves a Cloudflare challenge, cookies are cached for 30 minutes
- Subsequent pages on the same domain use cached cookies with curl_cffi (fast path)
- Only falls back to browser if cookies expire
- **Result:** First visit = 5-8 seconds, subsequent pages = 1-2 seconds

### Hidden JSON API Detection
- Before scraping any site, checks 10 common API paths:
  - `/api/contacts`, `/api/staff`, `/api/team`
  - `/wp-json/wp/v2/users`
  - `/api/members`, `/.json`, `/data.json`
- If site returns JSON directly → 10x faster, 100% accurate, no HTML parsing needed

---

## Lead Sources

| Source | Method | What You Get |
|--------|--------|-------------|
| Company Websites | 5-tier scraper | Name, email, phone, title |
| LinkedIn X-Ray | `site:linkedin.com/in` via DDG | Name, title, company, LinkedIn URL, email (if public) |
| Google Dorking | DDG + LLM parsing | Emails from social bios, PDFs, contact pages |
| Reddit | PRAW official API | Business owners who posted contact info |
| Quora | Playwright scraping | Professionals who listed email in bio/answers |
| Instagram | `site:instagram.com "@gmail.com"` dork | Public email from bio |
| PDF Directories | `filetype:pdf` dork | Staff lists, faculty directories |

---

## What We've Improved (Before vs After)

| Feature | Before | After |
|---------|--------|-------|
| Scraper tiers | 1 (requests only) | 5 (Tinyfish → curl_cffi → Camoufox → Playwright → BS4) |
| User agents | 1 fixed | 5 rotating |
| Retries | 1 attempt | 3 with Poisson backoff |
| BS4 extraction | Basic cleanup | 7-layer deep extraction |
| Processing | Sequential (1 site at a time) | 3 parallel workers |
| Duplicate detection | URL string only | Root domain dedup |
| Same company leads | Multiple counted | 1 best contact kept |
| LLM extraction | `with_structured_output` (silent fails) | Manual JSON parsing |
| Query generation | Always "B2B startup" framing | Respects exact user input |
| Email validation | Loose regex (caught filenames) | Strict + throwaway filter |
| Obfuscated emails | Not handled | Fixed automatically |
| Lead sources | Company websites only | 7 sources |
| Blocked sites (403) | Failed permanently | Camoufox/curl_cffi bypass |
| JS-rendered pages | Empty result | Playwright renders JS |

---

## LinkedIn — Honest Status

**What you get via X-Ray:**
- ✅ Full Name
- ✅ Job Title
- ✅ Company Name
- ✅ LinkedIn Profile URL
- ⚠️ Email — only if publicly listed (~10-15% of profiles)

**Why direct LinkedIn scraping is not possible:**
- LinkedIn uses behavioral analysis + IP reputation + login walls
- Even paid tools like PhantomBuster get banned regularly
- The X-Ray approach searches Google's cached index of public profiles
- Zero LinkedIn contact → zero ban risk

**Workaround for missing emails:**
When email is not on LinkedIn profile, the system uses the company name to scrape the company's official website and find the email there — which happens automatically in Stage 2.

---

## Key Differentiators vs Competitors

### vs Apollo.io / Hunter.io / ZoomInfo
| Feature | Apollo.io | RGTVetrex |
|---------|-----------|-----------|
| Cost per lead | $0.10 - $0.50 | Near zero (API costs only) |
| Email sending | Separate tool needed | Built-in |
| Personalization | Template-based | AI-written per person |
| Human approval | Not available | Full approval gate |
| Lead memory | Basic CRM | Neo4j graph (permanent) |
| Custom sources | No | Reddit, Quora, PDFs, X-Ray |

### vs Manual Outreach
| Metric | Manual | RGTVetrex |
|--------|--------|-----------|
| Time per day | 2-3 hours | 10 minutes (just review) |
| Leads per day | 20-30 | Up to 100 |
| Duplicates | Common | Zero (Neo4j memory) |
| Email quality | Variable | AI-personalized always |
| Follow-ups | Easy to forget | Auto-scheduled |

---

## ROI Summary

- **Setup time:** 10 minutes per campaign
- **Review time:** 5-10 minutes (human approval gate)
- **Cost:** API costs only (LLMs mostly free tier)
- **Output:** Up to 100 qualified leads/day with personalized emails ready to send
- **No per-lead pricing** — unlike Apollo ($0.10-0.50/lead), costs stay flat regardless of volume

---

## Running the System

**Backend:**
```
cd lead-outbound-engine
venv\Scripts\activate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```
cd lead-outbound-engine\frontend-web
npm run dev
```

**URLs:**
- Backend API: `http://localhost:8000`
- Frontend Dashboard: `http://localhost:5173`
- API Docs: `http://localhost:8000/docs`

---

*Built by Raghvendra Goyal — RGTVetrex*
*Version: July 2026*
