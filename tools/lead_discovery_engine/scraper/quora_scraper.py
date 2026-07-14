"""
quora_scraper.py
----------------
Extracts leads from Quora search results and answer pages.

Strategy:
  1. Search Quora via Google (site:quora.com query) using Tinyfish/DDG
  2. Scrape each Quora answer page with Playwright (Quora requires JS)
  3. Extract answerer names, bios, credentials, and any email/website
  4. Return structured lead dicts

Quora does NOT have a public API. This uses web scraping of public pages only.
"""

from __future__ import annotations

import re
import time
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from tools.lead_discovery_engine.extractor.regex_extractor import RegexExtractor
from tools.lead_discovery_engine.scraper.playwright_scraper import _try_playwright, PlaywrightScraper
from tools.lead_discovery_engine.utils.logger import get_logger

logger = get_logger(__name__)
regex = RegexExtractor()

_SCRAPER = PlaywrightScraper()

# Quora credential/bio patterns
_CREDENTIAL_RE = re.compile(
    r"(?:CEO|CTO|Founder|Director|Manager|Engineer|Consultant|"
    r"Professor|Teacher|Principal|Owner|Partner|VP|Head of|"
    r"MD|Doctor|Lawyer|Advocate|CA|CS)\b.{0,80}",
    re.IGNORECASE,
)


def _parse_quora_page(html_or_text: str, url: str) -> list[dict]:
    """
    Extract lead candidates from a Quora answer page.
    Works on both rendered HTML and Tinyfish markdown.
    """
    leads = []

    # Plain text / markdown from Tinyfish
    is_plain = html_or_text.count("<") / max(len(html_or_text), 1) < 0.05

    if is_plain:
        text = html_or_text
        emails = regex.extract_emails(text)
        phones = regex.extract_phones(text)
        # Find credential lines
        cred_matches = _CREDENTIAL_RE.findall(text)
        for i, email in enumerate(emails[:5]):
            leads.append({
                "full_name": "Quora User",
                "job_title": cred_matches[i].strip() if i < len(cred_matches) else "Professional",
                "email": email,
                "phone": phones[i] if i < len(phones) else None,
                "company_name": url,
                "source": "quora",
                "confidence_score": 0.65,
            })
        return leads

    # HTML path — use BeautifulSoup
    soup = BeautifulSoup(html_or_text, "html.parser")

    # Quora answer blocks
    answer_blocks = (
        soup.find_all("div", class_=re.compile(r"answer", re.I)) or
        soup.find_all("div", attrs={"data-testid": re.compile(r"answer", re.I)}) or
        [soup]  # fallback: entire page
    )

    seen_emails: set[str] = set()

    for block in answer_blocks[:10]:
        text = block.get_text(" ", strip=True)

        # Author name from nearby span/div
        name_el = (
            block.find("span", class_=re.compile(r"name|author|user", re.I)) or
            block.find("a", class_=re.compile(r"name|author|profile", re.I))
        )
        name = name_el.get_text(strip=True) if name_el else "Quora User"

        # Credential from bio line
        cred_matches = _CREDENTIAL_RE.findall(text)
        job_title = cred_matches[0].strip() if cred_matches else "Professional"

        # mailto links
        for a in block.find_all("a", href=re.compile(r"^mailto:", re.I)):
            email = a["href"][7:].split("?")[0].strip()
            if email and email.lower() not in seen_emails:
                seen_emails.add(email.lower())
                leads.append({
                    "full_name": name,
                    "job_title": job_title,
                    "email": email,
                    "phone": None,
                    "company_name": url,
                    "source": "quora",
                    "confidence_score": 0.75,
                })

        # Regex emails in text
        for email in regex.extract_emails(text)[:3]:
            if email.lower() not in seen_emails:
                seen_emails.add(email.lower())
                leads.append({
                    "full_name": name,
                    "job_title": job_title,
                    "email": email,
                    "phone": regex.extract_phones(text)[0] if regex.extract_phones(text) else None,
                    "company_name": url,
                    "source": "quora",
                    "confidence_score": 0.65,
                })

    return leads


class QuoraLeadScraper:
    """
    Extracts leads from Quora public answer pages.
    """

    def search_leads(
        self,
        query: str,
        location: str = "",
        max_leads: int = 20,
    ) -> list[dict]:
        """
        Find leads on Quora for the given query and location.
        """
        search_q = f"site:quora.com {query} {location} email contact".strip()
        quora_urls = self._find_quora_urls(search_q, max_urls=10)

        leads: list[dict] = []
        seen_emails: set[str] = set()

        for url in quora_urls:
            if len(leads) >= max_leads:
                break

            logger.info(f"[Quora] Scraping: {url}")
            # Quora requires JS — use Playwright
            content = _try_playwright(url, timeout_ms=20000)
            if not content:
                # Fallback to Tinyfish/requests
                content = _SCRAPER.scrape(url, timeout=20000)

            if not content:
                logger.warning(f"[Quora] Could not fetch: {url}")
                continue

            page_leads = _parse_quora_page(content, url)
            for lead in page_leads:
                email = lead.get("email", "")
                if email and email.lower() in seen_emails:
                    continue
                if email:
                    seen_emails.add(email.lower())
                leads.append(lead)

            time.sleep(1.5)  # polite delay

        logger.info(f"[Quora] Found {len(leads)} leads for '{query}'")
        return leads

    def _find_quora_urls(self, search_query: str, max_urls: int = 10) -> list[str]:
        """Use Tinyfish search or DDG to find Quora answer page URLs."""
        import os
        import httpx
        from urllib.parse import quote

        urls: list[str] = []

        # Try Tinyfish search
        tinyfish_key = os.getenv("TINYFISH_API_KEY", "")
        if tinyfish_key:
            try:
                encoded = quote(search_query)
                with httpx.Client(timeout=20) as client:
                    resp = client.get(
                        f"https://api.search.tinyfish.ai?query={encoded}",
                        headers={"X-API-Key": tinyfish_key},
                    )
                    if resp.status_code == 200:
                        for r in resp.json().get("results", []):
                            u = r.get("url", "")
                            if "quora.com" in u:
                                urls.append(u)
            except Exception as e:
                logger.warning(f"[Quora] Tinyfish search failed: {e}")

        # DDG fallback
        if len(urls) < 3:
            try:
                from ddgs import DDGS
                ddgs = DDGS()
                for r in ddgs.text(search_query, max_results=max_urls):
                    u = r.get("href", "")
                    if "quora.com" in u and u not in urls:
                        urls.append(u)
            except Exception as e:
                logger.warning(f"[Quora] DDG search failed: {e}")

        return list(dict.fromkeys(urls))[:max_urls]
