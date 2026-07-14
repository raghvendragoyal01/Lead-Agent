"""
google_dork_scraper.py
----------------------
Finds leads using Google Dorking + LinkedIn X-Ray search.

Strategy:
  1. LLM generates smart Google dork strings for the target
  2. DDG executes dork searches (no API key needed, no ban risk)
  3. Tinyfish fetches high-value result pages
  4. LLM parses raw text and extracts structured leads

LinkedIn X-Ray:
  Google caches LinkedIn public profile snippets.
  Searching site:linkedin.com via Google/DDG returns name, title,
  company from cached profiles — without ever touching LinkedIn.
  No login, no ban, completely free.

Dork examples:
  site:linkedin.com/in "CEO" "Mumbai" "Healthcare"
  site:linkedin.com/in "founder" "SaaS" "Bangalore" "@gmail.com"
  site:instagram.com "real estate agent" "Mumbai" "@gmail.com"
  filetype:pdf "staff directory" "school" "Rajasthan" "@"
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional
from urllib.parse import quote

import httpx
from ddgs import DDGS

from tools.lead_discovery_engine.extractor.regex_extractor import RegexExtractor
from tools.lead_discovery_engine.utils.logger import get_logger

logger = get_logger(__name__)
regex = RegexExtractor()

# ---------------------------------------------------------------------------
# Generic dork templates
# ---------------------------------------------------------------------------

_DORK_TEMPLATES = [
    # Direct email exposure on social profiles
    'site:instagram.com "{target}" "{location}" "@gmail.com" OR "@yahoo.com" OR "@outlook.com"',
    # Staff/contact pages
    '"{target}" "{location}" "contact" "@gmail.com" OR "@yahoo.com" filetype:html',
    # PDF staff directories
    '"{target}" "{location}" "staff directory" OR "contact list" filetype:pdf "@"',
    # Plain email exposure
    '"{target}" "{location}" "email" "@gmail.com" OR "@yahoo.com" OR "@hotmail.com"',
    # India-specific
    '"{target}" "{location}" "contact us" "email" site:.in OR site:.org OR site:.edu',
]

# ---------------------------------------------------------------------------
# LinkedIn X-Ray dork templates
# These search Google/DDG for cached LinkedIn public profile data
# — zero LinkedIn logins, zero ban risk
# ---------------------------------------------------------------------------

_LINKEDIN_XRAY_TEMPLATES = [
    # Core X-Ray: profile pages with job title + location
    'site:linkedin.com/in "{title}" "{location}"',
    # With email hint — finds profiles that listed email publicly
    'site:linkedin.com/in "{title}" "{location}" "@gmail.com" OR "@yahoo.com" OR "@outlook.com"',
    # Company page employees
    'site:linkedin.com/in "{title}" "{location}" "at {target}"',
    # Indian professional profiles
    'site:linkedin.com/in "{title}" "{location}" India',
    # With contact keyword
    'site:linkedin.com/in "{title}" "{location}" "email" OR "contact" OR "reach"',
]

# Job title synonyms to broaden X-Ray coverage
_TITLE_EXPANSIONS: dict[str, list[str]] = {
    "school": ["Principal", "Vice Principal", "Head Teacher", "School Director",
               "Academic Director", "Admission Officer"],
    "college": ["Dean", "Principal", "Director", "HOD", "Professor",
                "Placement Officer", "Admission Coordinator"],
    "hospital": ["Medical Director", "CEO", "CMO", "Hospital Administrator"],
    "startup": ["Founder", "CEO", "CTO", "Co-Founder"],
    "real estate": ["Real Estate Agent", "Property Consultant", "Broker"],
    "restaurant": ["Owner", "Manager", "Restaurant Owner"],
    "software": ["CTO", "Founder", "Engineering Manager", "Tech Lead"],
    "default": ["CEO", "Founder", "Director", "Manager", "Owner"],
}


def _get_title_expansions(target: str) -> list[str]:
    """Return relevant job titles for the target niche."""
    t = target.lower()
    for key, titles in _TITLE_EXPANSIONS.items():
        if key in t:
            return titles
    return _TITLE_EXPANSIONS["default"]


def _fix_obfuscated(text: str) -> str:
    """Convert 'name [at] domain [dot] com' → 'name@domain.com'."""
    text = re.sub(r'\s*[\[\(]at[\]\)]\s*', '@', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*[\[\(]dot[\]\)]\s*', '.', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+@\s+', '@', text)
    text = re.sub(r'\s+\.\s+', '.', text)
    return text


def _llm_parse_leads(raw_text: str, target: str, location: str,
                     source_hint: str = "web") -> list[dict]:
    """
    Use the LLM to extract structured leads from raw dork/X-Ray result text.
    For LinkedIn X-Ray results, email may be absent — we still capture
    name + title + company which has value for manual outreach.
    """
    from config.llm_config import get_llm
    llm = get_llm(temperature=0.0)

    is_linkedin = "linkedin" in source_hint.lower()
    email_note = (
        "Email may not be present for LinkedIn results — that is OK, "
        "still extract name/title/company. Leave email as null if not found."
        if is_linkedin else
        "Try to find email — fix obfuscated ones like 'name at domain dot com'."
    )

    prompt = f"""You are a lead extraction AI.
Extract all people/businesses from the text below.
Target: {target} in {location}
Source type: {source_hint}

{email_note}

For each person found, extract:
- full_name
- job_title
- email (or null)
- phone (or null)
- company_name
- linkedin_url (if a linkedin.com/in URL is visible)
- source_url

Return ONLY a JSON array. No markdown, no explanation. If none found, return [].

Example:
[{{"full_name": "Raj Sharma", "job_title": "Principal", "email": null, \
"phone": null, "company_name": "DPS School", \
"linkedin_url": "https://linkedin.com/in/rajsharma", \
"source_url": "https://linkedin.com/in/rajsharma"}}]

TEXT:
{raw_text[:5000]}
"""
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        text = text.replace('```json', '').replace('```', '').strip()
        text = re.sub(r',\s*([\]}])', r'\1', text)
        match = re.search(r'(\[.*\])', text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            return data if isinstance(data, list) else []
        return []
    except Exception as e:
        logger.warning(f"[GoogleDork] LLM parse failed: {e}")
        return []


def _fetch_page(url: str) -> Optional[str]:
    """Fetch a URL using Tinyfish then requests fallback."""
    tinyfish_key = os.getenv("TINYFISH_API_KEY", "")
    if tinyfish_key:
        try:
            with httpx.Client(timeout=20) as client:
                resp = client.post(
                    "https://api.fetch.tinyfish.ai",
                    headers={"X-API-Key": tinyfish_key,
                             "Content-Type": "application/json"},
                    json={"urls": [url]},
                )
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    if results and results[0].get("text"):
                        return results[0]["text"]
        except Exception:
            pass
    try:
        import requests
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/137.0.0.0"
        }, verify=False)
        if r.status_code == 200:
            return r.text[:8000]
    except Exception:
        pass
    return None


def _search_ddg(dork: str, max_results: int = 10) -> str:
    """Execute a dork via DuckDuckGo, return combined snippets + fetched pages."""
    try:
        ddgs = DDGS()
        results = ddgs.text(dork, max_results=max_results)
        combined = ""
        for r in results:
            snippet = r.get("body", "") or r.get("snippet", "")
            url     = r.get("href", "")
            title   = r.get("title", "")
            combined += f"\nTitle: {title}\nURL: {url}\nSnippet: {snippet}\n---"

            # Fetch full content for high-value pages
            fetch_this = (
                url and (
                    ".pdf" in url.lower()
                    or "@" in snippet
                    or "email" in snippet.lower()
                    or "linkedin.com/in" in url
                )
            )
            if fetch_this:
                page = _fetch_page(url)
                if page:
                    combined += f"\nFULL PAGE:\n{page[:3000]}\n"

        return combined
    except Exception as e:
        logger.warning(f"[GoogleDork] DDG failed for '{dork}': {e}")
        return ""


def _build_lead(item: dict, all_text: str, target: str,
                seen_emails: set[str]) -> Optional[dict]:
    """Validate and normalise a parsed lead dict."""
    email = _fix_obfuscated((item.get("email") or "").strip())
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        email = ""

    # Last-resort regex scan if LLM missed an email
    if not email:
        for e in regex.extract_emails(all_text)[:3]:
            if e.lower() not in seen_emails:
                email = e
                break

    phone    = item.get("phone") or None
    linkedin = item.get("linkedin_url") or None

    # Must have at least one contact signal
    if not email and not phone and not linkedin:
        return None

    if email and email.lower() in seen_emails:
        return None
    if email:
        seen_emails.add(email.lower())

    return {
        "full_name":        item.get("full_name") or "Contact",
        "job_title":        item.get("job_title") or "Professional",
        "email":            email or None,
        "phone":            phone,
        "company_name":     item.get("company_name") or target,
        "industry":         target,
        "linkedin_url":     linkedin,
        "source":           item.get("source_url") or "google_dork",
        "confidence_score": 0.80 if email else (0.65 if linkedin else 0.45),
    }


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class GoogleDorkScraper:
    """
    Finds leads via:
      1. Generic Google Dorks  (websites, PDFs, Instagram, etc.)
      2. LinkedIn X-Ray Search (site:linkedin.com/in via Google/DDG)
    """

    def search_leads(
        self,
        target: str,
        location: str = "",
        max_leads: int = 20,
        custom_dorks: list[str] | None = None,
        linkedin_xray: bool = True,
    ) -> list[dict]:
        """
        Run all dork searches and return deduplicated leads.
        """
        leads: list[dict] = []
        seen_emails: set[str] = set()

        # ── 1. Generic dorks ─────────────────────────────────────────
        generic_dorks = custom_dorks or self._generic_dorks(target, location)
        generic_text = ""
        for dork in generic_dorks:
            if len(leads) >= max_leads:
                break
            logger.info(f"[GoogleDork] {dork}")
            generic_text += f"\n\n[DORK: {dork}]\n{_search_ddg(dork)}"
            time.sleep(1.2)

        if generic_text.strip():
            parsed = _llm_parse_leads(generic_text, target, location, "web")
            for item in parsed:
                if len(leads) >= max_leads:
                    break
                lead = _build_lead(item, generic_text, target, seen_emails)
                if lead:
                    leads.append(lead)

        # ── 2. LinkedIn X-Ray ─────────────────────────────────────────
        if linkedin_xray and len(leads) < max_leads:
            xray_leads = self._linkedin_xray(target, location,
                                             max_leads - len(leads),
                                             seen_emails)
            leads.extend(xray_leads)

        logger.info(f"[GoogleDork+LinkedIn] {len(leads)} total leads for "
                    f"'{target}' in '{location}'")
        return leads

    # ------------------------------------------------------------------

    def _generic_dorks(self, target: str, location: str) -> list[str]:
        return [
            t.replace("{target}", target).replace("{location}", location)
            for t in _DORK_TEMPLATES
        ]

    def _linkedin_xray(
        self,
        target: str,
        location: str,
        max_leads: int,
        seen_emails: set[str],
    ) -> list[dict]:
        """
        LinkedIn X-Ray: use Google/DDG to search site:linkedin.com/in
        for public profile snippets — no LinkedIn login, no ban risk.
        """
        titles = _get_title_expansions(target)
        leads: list[dict] = []
        xray_text = ""

        logger.info(f"[LinkedIn X-Ray] Starting for '{target}' in '{location}' "
                    f"with {len(titles)} title variations")

        for title in titles:
            if len(leads) >= max_leads:
                break
            for template in _LINKEDIN_XRAY_TEMPLATES[:3]:  # top 3 templates per title
                if len(leads) >= max_leads:
                    break
                dork = (template
                        .replace("{title}", title)
                        .replace("{location}", location)
                        .replace("{target}", target))
                logger.info(f"[LinkedIn X-Ray] {dork}")
                chunk = _search_ddg(dork, max_results=8)
                if chunk:
                    xray_text += f"\n\n[X-RAY: {title}]\n{chunk}"
                time.sleep(1.5)  # slightly longer delay for LinkedIn dorks

        if not xray_text.strip():
            return leads

        parsed = _llm_parse_leads(xray_text, target, location, "linkedin_xray")
        for item in parsed:
            if len(leads) >= max_leads:
                break
            lead = _build_lead(item, xray_text, target, seen_emails)
            if lead:
                lead["source"] = lead.get("linkedin_url") or "linkedin_xray"
                leads.append(lead)

        logger.info(f"[LinkedIn X-Ray] {len(leads)} leads extracted")
        return leads
