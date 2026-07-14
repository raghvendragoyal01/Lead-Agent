"""
multi_page_crawler.py
---------------------
Crawls the highest-value pages of a company website and merges
their content into a single document for the LLM extractor.

Key improvements:
- BS4 used at full depth for signal extraction
- Extracts mailto/tel links, JSON-LD, microdata, meta tags
- Detects plain-text (Tinyfish markdown) and skips HTML parsing
- Polite crawl delay between pages
"""

from __future__ import annotations

import json
import re
import time
from typing import List

from bs4 import BeautifulSoup, NavigableString

from tools.lead_discovery_engine.cleaner.html_cleaner import HTMLCleaner
from tools.lead_discovery_engine.discovery.link_discovery import LinkDiscovery
from tools.lead_discovery_engine.discovery.page_prioritizer import PagePrioritizer
from tools.lead_discovery_engine.extractor.regex_extractor import RegexExtractor
from tools.lead_discovery_engine.schemas.page_schema import DiscoveredPage
from tools.lead_discovery_engine.scraper.playwright_scraper import PlaywrightScraper


class MultiPageCrawler:
    """
    Crawls the most important pages of a company website
    and merges only the highest-signal content into one document.
    """

    PAGE_TEXT_LIMIT  = 6000
    TOTAL_TEXT_LIMIT = 30000
    SIGNAL_LINE_LIMIT = 50
    PAGE_DELAY_S = 0.6

    KEY_PAGE_HINTS = {
        "contact": ("contact", "get-in-touch", "reach-us", "reach-out",
                    "connect", "enquiry", "inquiry", "support"),
        "about":   ("about", "company", "who-we-are", "our-story",
                    "overview", "profile"),
        "team":    ("team", "leadership", "management", "founder",
                    "people", "staff", "directors", "board"),
    }

    SIGNAL_KEYWORDS = (
        "contact", "email", "phone", "call", "address", "office",
        "headquarters", "support", "sales", "reach", "connect",
        "enquiry", "inquiry", "director", "founder", "ceo", "cto",
        "manager", "principal", "admission",
    )

    def __init__(self):
        self.scraper    = PlaywrightScraper()
        self.cleaner    = HTMLCleaner()
        self.discovery  = LinkDiscovery()
        self.prioritizer = PagePrioritizer()
        self.regex      = RegexExtractor()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _trim_text(self, text: str, limit: int) -> str:
        text = (text or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit].rsplit(" ", 1)[0].strip()

    def _is_plain_text(self, content: str) -> bool:
        """Detect if the content is already plain text / markdown (from Tinyfish)."""
        return content.count("<") / max(len(content), 1) < 0.05

    def _extract_signals(self, content: str) -> str:
        """
        Maximum-depth signal extraction using BeautifulSoup.

        Works on both raw HTML and plain-text (Tinyfish markdown):
        - plain text: regex scan for emails/phones + keyword lines
        - HTML: full BS4 parse with mailto, tel, JSON-LD, microdata, meta
        """
        signal_lines: list[str] = []
        seen: set[str] = set()

        def add(line: str):
            n = " ".join(line.split())
            if n and n.lower() not in seen and len(n) > 2:
                seen.add(n.lower())
                signal_lines.append(n)

        # ── Plain text fast path ──────────────────────────────────────
        if self._is_plain_text(content):
            for email in self.regex.extract_emails(content)[:10]:
                add(f"Email: {email}")
            for phone in self.regex.extract_phones(content)[:5]:
                add(f"Phone: {phone}")
            for line in content.splitlines():
                ln = " ".join(line.split())
                if not ln:
                    continue
                if "@" in ln or any(k in ln.lower() for k in self.SIGNAL_KEYWORDS):
                    add(ln)
                if len(signal_lines) >= self.SIGNAL_LINE_LIMIT:
                    break
            return "\n".join(signal_lines[:self.SIGNAL_LINE_LIMIT])

        # ── HTML deep parse ───────────────────────────────────────────
        soup = BeautifulSoup(content, "html.parser")

        # 1. mailto / tel links
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            label = a.get_text(" ", strip=True)
            lh = href.lower()
            if lh.startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if email:
                    add(f"Email: {email}")
            elif lh.startswith("tel:"):
                add(f"Phone: {href[4:].strip()}")
            elif label and any(k in label.lower() for k in self.SIGNAL_KEYWORDS):
                add(f"Link: {label} → {href}")

        # 2. JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                flat = json.dumps(data, ensure_ascii=False)
                # Pull out emails/phones from JSON-LD
                for email in self.regex.extract_emails(flat)[:5]:
                    add(f"Email (JSON-LD): {email}")
                for phone in self.regex.extract_phones(flat)[:3]:
                    add(f"Phone (JSON-LD): {phone}")
                # Named entities
                for key in ("name", "legalName", "founder", "employee"):
                    if key in data:
                        add(f"JSON-LD {key}: {str(data[key])[:100]}")
            except Exception:
                pass

        # 3. Microdata (itemscope / itemprop)
        for el in soup.find_all(itemprop=True):
            prop = el.get("itemprop", "").lower()
            val = (el.get("content") or el.get_text(" ", strip=True))[:200].strip()
            if val and any(k in prop for k in (
                "email", "phone", "telephone", "name", "jobtitle",
                "organization", "addresslocality", "addressregion", "url"
            )):
                add(f"Microdata {prop}: {val}")

        # 4. Meta tags
        for meta in soup.find_all("meta"):
            name = (meta.get("name") or meta.get("property") or "").lower()
            content_val = (meta.get("content") or "").strip()
            if not content_val:
                continue
            if any(k in name for k in (
                "email", "phone", "contact", "author", "publisher",
                "og:site_name", "og:title", "description"
            )):
                add(f"Meta {name}: {content_val[:200]}")

        # 5. <address> tags — HTML spec says these contain contact info
        for addr in soup.find_all("address"):
            text = addr.get_text(" ", strip=True)
            if text:
                add(f"Address block: {text[:300]}")

        # 6. Visible text lines containing signal keywords
        visible = soup.get_text(separator="\n", strip=True)
        for email in self.regex.extract_emails(visible)[:10]:
            add(f"Email: {email}")
        for phone in self.regex.extract_phones(visible)[:5]:
            add(f"Phone: {phone}")

        for line in visible.splitlines():
            ln = " ".join(line.split())
            if not ln or len(ln) < 4:
                continue
            if "@" in ln or any(k in ln.lower() for k in self.SIGNAL_KEYWORDS):
                add(ln)
            if len(signal_lines) >= self.SIGNAL_LINE_LIMIT:
                break

        return "\n".join(signal_lines[:self.SIGNAL_LINE_LIMIT])

    def _build_page_packet(self, page_label: str, page_url: str, content: str) -> str:
        """Build a labelled text packet for one page."""
        # If content is plain text (Tinyfish), skip HTML cleaning
        if self._is_plain_text(content):
            cleaned_text = self._trim_text(content, self.PAGE_TEXT_LIMIT)
        else:
            cleaned_text = self._trim_text(
                self.cleaner.clean(content), self.PAGE_TEXT_LIMIT
            )

        signal_text = self._extract_signals(content)

        sections = [f"[PAGE: {page_label}] {page_url}"]
        if signal_text:
            sections.append("[HIGH SIGNAL CONTACT DATA]")
            sections.append(signal_text)
        if cleaned_text:
            sections.append("[CLEAN PAGE CONTENT]")
            sections.append(cleaned_text)

        return "\n".join(sections).strip()

    def _select_priority_pages(
        self,
        prioritized: List[DiscoveredPage],
        max_pages: int,
    ) -> List[DiscoveredPage]:
        selected: List[DiscoveredPage] = []
        seen_urls: set[str] = set()

        # First pass: guarantee key page types are included
        for hints in self.KEY_PAGE_HINTS.values():
            for page in prioritized:
                key = str(page.url)
                page_lower = key.lower()
                text_lower = (page.text or "").lower()
                if key in seen_urls:
                    continue
                if any(hint in page_lower or hint in text_lower for hint in hints):
                    selected.append(page)
                    seen_urls.add(key)
                    break

        # Second pass: fill remaining slots by score
        for page in prioritized:
            if len(selected) >= max_pages:
                break
            key = str(page.url)
            if key in seen_urls or page.score <= 0:
                continue
            selected.append(page)
            seen_urls.add(key)

        return selected[:max_pages]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def crawl(self, homepage_url: str, max_pages: int = 6) -> str:
        homepage_content = self.scraper.scrape(homepage_url)
        if not homepage_content:
            self.scraper.close_browser()
            return ""

        # Discover internal links (only works on HTML, not markdown)
        if not self._is_plain_text(homepage_content):
            discovered = self.discovery.discover(homepage_content, homepage_url)
        else:
            discovered = []

        prioritized    = self.prioritizer.prioritize(discovered)
        selected_pages = self._select_priority_pages(prioritized, max_pages)

        merged_content: list[str] = []

        homepage_packet = self._build_page_packet(
            page_label="homepage",
            page_url=homepage_url,
            content=homepage_content,
        )
        if homepage_packet:
            merged_content.append(homepage_packet)

        visited: set[str] = set()

        for page in selected_pages:
            page_url = str(page.url)
            if page_url == homepage_url or page_url in visited:
                continue

            time.sleep(self.PAGE_DELAY_S)
            content = self.scraper.scrape(page_url)
            if not content:
                continue

            packet = self._build_page_packet(
                page_label=page.text or "internal-page",
                page_url=page_url,
                content=content,
            )
            if packet:
                merged_content.append(packet)
            visited.add(page_url)

        self.scraper.close_browser()

        final = "\n\n".join(b for b in merged_content if b)
        return self._trim_text(final, self.TOTAL_TEXT_LIMIT)
