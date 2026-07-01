# 🚀 Lead Discovery Engine

A modular AI-powered Lead Discovery Engine that crawls company websites, extracts structured business information, validates the results, and generates clean JSON outputs for B2B lead generation.

The project combines **web crawling**, **HTML processing**, **regex extraction**, and **Google Gemini AI** to automatically discover valuable company information from public websites.

---

# 📌 Features

✅ Multi-page website crawling using Playwright

✅ JavaScript-rendered HTML scraping

✅ Intelligent internal page discovery

✅ Priority-based page crawling

✅ HTML cleaning and text extraction

✅ AI-powered information extraction using Google Gemini

✅ Email and phone extraction using Regex

✅ Contact validation and duplicate removal

✅ Structured output using Pydantic models

✅ Modular and extensible architecture

✅ JSON export for downstream applications

---

# 🎯 Problem Statement

Finding structured company information manually is time-consuming and inconsistent.

This project automates the process by:

- Crawling company websites
- Understanding their content
- Extracting business information
- Producing structured lead data

This can be used for:

- Lead Generation
- Sales Intelligence
- CRM Population
- Company Research
- Business Analytics

---

# 🏗️ System Architecture

```
                 Company Website
                        │
                        ▼
            Playwright Web Scraper
                        │
                        ▼
               HTML Cleaner
                        │
                        ▼
             Link Discovery Engine
                        │
                        ▼
            Multi-Page Website Crawl
                        │
                        ▼
        +-----------------------------+
        |                             |
        ▼                             ▼
 Regex Extractor              Gemini AI Extractor
        |                             |
        +-------------+---------------+
                      │
                      ▼
              Lead Validator
                      │
                      ▼
               Structured Lead
                      │
                      ▼
                 JSON Output
```

---

# 📂 Project Structure

```
lead-discovery-engine/

│
├── app/
│   ├── cleaner/
│   ├── config/
│   ├── discovery/
│   ├── extractor/
│   ├── pipeline/
│   ├── prompts/
│   ├── schemas/
│   ├── scraper/
│   ├── search/
│   ├── utils/
│   └── validator/
│
├── tests/
│
├── result.json
├── requirements.txt
└── README.md
```

---

# ⚙️ Technologies Used

- Python 3.12
- Playwright
- BeautifulSoup4
- Trafilatura
- Pydantic v2
- Google Gemini API
- Regex
- dotenv

---

# 🧠 Pipeline

```
Website URL
      │
      ▼
Search & Validation
      │
      ▼
Playwright Scraper
      │
      ▼
HTML Cleaning
      │
      ▼
Internal Link Discovery
      │
      ▼
Priority Page Selection
      │
      ▼
Multi-page Crawl
      │
      ▼
Gemini AI Extraction
      │
      ▼
Regex Extraction
      │
      ▼
Lead Validation
      │
      ▼
Structured Lead Object
      │
      ▼
JSON Output
```

---

# 📦 Installation

Clone the repository

```bash
git clone https://github.com/<your-username>/lead-discovery-engine.git

cd lead-discovery-engine
```

Install dependencies

```bash
pip install -r requirements.txt
```

Install Playwright browser

```bash
playwright install
```

Create a `.env` file

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

---

# ▶️ Usage

Run the complete pipeline

```bash
python -m tests.test_complete_pipeline
```

---

# 📄 Sample Output

```json
{
    "company_name": "Apollo Hospitals",
    "website": "https://www.apollohospitals.com/",
    "industry": "Healthcare",
    "description": "...",
    "address": {
        "country": "India",
        "city": "Chennai"
    },
    "contacts": [
        {
            "name": "SM Krishnan",
            "designation": "Company Secretary & Compliance Officer",
            "email": "krishnan_sm@apollohospitals.com",
            "phone": "+91-44-2829 0956"
        }
    ]
}
```

---

# ✅ Current Capabilities

- Multi-page crawling
- AI-based company understanding
- Contact extraction
- Email extraction
- Phone extraction
- Duplicate removal
- JSON generation
- Modular architecture

---

# ⚠️ Limitations

- Social links are extracted only if they are explicitly available on the crawled website.
- Employee size is intentionally excluded to avoid AI hallucination.
- Current implementation uses the `google-generativeai` SDK. Migration to the newer `google-genai` SDK is planned for a future release.

---

# 🚀 Future Improvements

- Async crawling
- FastAPI REST API
- PostgreSQL integration
- Docker deployment
- Social media extraction from additional pages
- Company logo extraction
- Technology stack detection
- CRM integration
- Batch website processing
- Migration to Google GenAI SDK

---

# 📊 Example Workflow

```
Website
   │
   ▼
Crawler
   │
   ▼
Cleaner
   │
   ▼
Gemini AI
   │
   ▼
Validator
   │
   ▼
Lead JSON
```

---

# 👨‍💻 Author

**Suvajit Majhi**

B.Tech CSE (IoT)

University of Engineering & Management, Kolkata

Interested in:

- Artificial Intelligence
- Machine Learning
- Data Science
- Cybersecurity
- Software Development

---

# ⭐ If you found this project useful

Please consider giving it a ⭐ on GitHub.