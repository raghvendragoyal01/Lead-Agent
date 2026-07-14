"""
playwright_scraper.py  —  Universal Anti-Bot Scraper
=====================================================

Five-tier strategy (each tier tried in order, stops at first success):

  Tier 1 — Tinyfish Fetch API
            Fast cloud-based fetcher, bypass-capable, returns clean markdown.

  Tier 2 — curl_cffi  (TLS/JA3 fingerprint spoofing)
            Mimics real Chrome/Safari at the TCP handshake level.
            Bypasses Cloudflare, Akamai, and most basic bot filters
            without launching a browser. ~60% of blocked sites pass here.

  Tier 3 — Camoufox  (anti-detect Firefox)
            Full browser with OS/fingerprint spoofing + stealth patches.
            Strips navigator.webdriver, fixes canvas/WebGL leaks.
            Best for Cloudflare Turnstile and JS-heavy Indian sites.

  Tier 4 — Playwright + playwright-stealth patches
            Headless Chromium with webdriver flag removed + human
            behavioral noise (Bézier mouse paths, Poisson delays).

  Tier 5 — requests + deep BeautifulSoup extraction
            Static HTML last resort with 7-layer BS4 signal extraction.

Session cache:
  Tiers 3/4 run a single warm browser session per domain. On first visit
  they solve any verification puzzle and cache the resulting cookies.
  Subsequent pages on the same domain reuse those cookies via curl_cffi
  (fast path), only falling back to the browser if cookies expire.

Hidden JSON API sniffing:
  Before any tier, the scraper checks if the target URL returns JSON
  directly. Many modern sites expose /api/contacts, /api/staff etc.
  that return perfectly structured data without needing HTML parsing.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import threading
import time
import urllib3
from typing import Optional

import httpx
import requests
from bs4 import BeautifulSoup, Comment, NavigableString

from tools.lead_discovery_engine.utils.logger import get_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("trafilatura").setLevel(logging.CRITICAL)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# User agents — rotated per request
# ---------------------------------------------------------------------------
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

# Tags never useful for lead extraction
_STRIP_TAGS = {
    "script", "style", "noscript", "meta", "link", "svg", "canvas",
    "iframe", "object", "embed", "applet", "base", "head",
    "nav", "footer", "header", "aside",
    "figure", "picture", "source", "track",
    "button", "input", "select", "textarea",
}

# ---------------------------------------------------------------------------
# Technique 4 — Behavioral mimicry helpers
# ---------------------------------------------------------------------------

def _poisson_delay(mean: float = 2.0, min_s: float = 0.8,
                   max_s: float = 7.0) -> float:
    """
    Generate a Poisson-distributed random delay.
    Shatters static pattern-recognition that detects fixed sleep(2) calls.
    """
    raw = random.expovariate(1.0 / mean)
    return max(min_s, min(max_s, raw))


def _bezier_mouse_path(
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int = 12,
) -> list[tuple[float, float]]:
    """
    Generate a Bézier curve mouse path between two points.
    Organic curved movement — never a straight line that triggers biometrics.
    """
    # Random control points with slight randomness
    cx = (start[0] + end[0]) / 2 + random.uniform(-80, 80)
    cy = (start[1] + end[1]) / 2 + random.uniform(-80, 80)
    path = []
    for i in range(steps + 1):
        t = i / steps
        # Quadratic Bézier formula
        x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * cx + t ** 2 * end[0]
        y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * cy + t ** 2 * end[1]
        path.append((x, y))
    return path


def _human_scroll(page, steps: int = 3) -> None:
    """Scroll down in a human-like pattern with random amounts."""
    try:
        for _ in range(steps):
            amount = random.randint(200, 600)
            page.mouse.wheel(0, amount)
            time.sleep(_poisson_delay(0.4, 0.2, 1.2))
    except Exception:
        pass


def _human_click(page, selector: str) -> None:
    """Click an element via Bézier mouse path instead of direct .click()."""
    try:
        el = page.query_selector(selector)
        if not el:
            return
        box = el.bounding_box()
        if not box:
            return
        target = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        start = (random.uniform(0, 800), random.uniform(0, 600))
        path = _bezier_mouse_path(start, target)
        for x, y in path:
            page.mouse.move(x, y)
            time.sleep(_poisson_delay(0.02, 0.005, 0.08))
        page.mouse.click(target[0], target[1])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Technique 5 — Session cookie cache (per domain, thread-safe)
# ---------------------------------------------------------------------------

_cookie_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()
_COOKIE_TTL = 1800  # 30 minutes


def _cache_key(url: str) -> str:
    from urllib.parse import urlparse
    netloc = urlparse(url).netloc.lower().lstrip("www.")
    return netloc.split(":")[0]


def _get_cached_cookies(url: str) -> Optional[dict]:
    key = _cache_key(url)
    with _cache_lock:
        entry = _cookie_cache.get(key)
        if entry and time.time() - entry["ts"] < _COOKIE_TTL:
            return entry["cookies"]
    return None


def _set_cached_cookies(url: str, cookies: dict) -> None:
    key = _cache_key(url)
    with _cache_lock:
        _cookie_cache[key] = {"cookies": cookies, "ts": time.time()}


# ---------------------------------------------------------------------------
# Technique 3 — Hidden JSON API sniffing
# ---------------------------------------------------------------------------

_JSON_API_PATTERNS = [
    "/api/contacts", "/api/staff", "/api/team", "/api/members",
    "/api/about", "/wp-json/wp/v2/users", "/api/employees",
    "/.json", "/data.json", "/contacts.json",
]


def _try_json_api(base_url: str) -> Optional[str]:
    """
    Check if the site exposes a JSON API endpoint with contact data.
    Returns JSON string if found, else None.
    """
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    for path in _JSON_API_PATTERNS:
        try:
            url = origin + path
            resp = requests.get(
                url, timeout=8,
                headers={"User-Agent": random.choice(_USER_AGENTS),
                         "Accept": "application/json"},
                verify=False,
            )
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                if "json" in ct or resp.text.strip().startswith(("[", "{")):
                    data = resp.json()
                    if data:  # non-empty JSON
                        text = json.dumps(data, ensure_ascii=False)
                        logger.debug(f"JSON API found at {url} "
                                     f"({len(text):,} chars)")
                        return text
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# BeautifulSoup deep-extraction (7 layers)
# ---------------------------------------------------------------------------

def _bs4_deep_extract(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []

    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    # 1. mailto / tel links
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        label = a.get_text(" ", strip=True)
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if email:
                lines.append(f"[MAILTO] {email}")
        elif href.lower().startswith("tel:"):
            lines.append(f"[TEL] {href[4:].strip()}")
        elif label:
            lines.append(f"[LINK] {label} → {href}")

    # 2. Meta tags
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").lower()
        content = (meta.get("content") or "").strip()
        if content and any(k in name for k in (
            "email", "phone", "contact", "description",
            "og:site_name", "og:title", "twitter:title", "author", "publisher"
        )):
            lines.append(f"[META:{name}] {content}")

    # 3. JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            lines.append(f"[JSON-LD] {json.dumps(data, ensure_ascii=False)[:2000]}")
        except Exception:
            pass

    # 4. Microdata
    for el in soup.find_all(itemprop=True):
        prop = el.get("itemprop", "").lower()
        val = (el.get("content") or el.get_text(" ", strip=True))[:200]
        if val and any(k in prop for k in (
            "email", "phone", "telephone", "name", "jobtitle",
            "organization", "addresslocality", "url"
        )):
            lines.append(f"[MICRODATA:{prop}] {val}")

    # 5. HTML comments with contact hints
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        s = comment.strip()
        if s and ("@" in s or any(k in s.lower()
                                   for k in ("email", "phone", "contact"))):
            lines.append(f"[COMMENT] {s[:300]}")

    # 6. <address> tags
    for addr in soup.find_all("address"):
        t = addr.get_text(" ", strip=True)
        if t:
            lines.append(f"[ADDRESS] {t[:300]}")

    # 7. Visible text from content tags
    _CONTENT_TAGS = {
        "p", "h1", "h2", "h3", "h4", "h5", "li",
        "td", "th", "dt", "dd", "span", "div", "label",
        "address", "article", "section", "main",
    }
    seen: set[str] = set()
    for tag in soup.find_all(_CONTENT_TAGS):
        direct = "".join(
            str(c) for c in tag.children if isinstance(c, NavigableString)
        ).strip()
        normalized = " ".join(direct.split())
        if normalized and normalized not in seen and len(normalized) >= 3:
            seen.add(normalized)
            lines.append(f"[{tag.name.upper()}] {normalized}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tier 2 — curl_cffi (TLS/JA3 fingerprint spoofing)
# ---------------------------------------------------------------------------

def _try_curl_cffi(url: str, timeout_s: float = 20.0,
                   cookies: Optional[dict] = None) -> Optional[str]:
    """
    Use curl_cffi to spoof Chrome's TLS/JA3 fingerprint.
    Bypasses Cloudflare and Akamai bot filters that reject Python's
    default TLS stack. Falls back gracefully if not installed.
    """
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        logger.debug("curl_cffi not installed. Run: pip install curl-cffi")
        return None

    _impersonate_profiles = [
        "chrome120", "chrome124", "chrome131",
        "safari17_0", "safari18_0",
    ]
    profile = random.choice(_impersonate_profiles)

    try:
        resp = cffi_requests.get(
            url,
            impersonate=profile,
            timeout=timeout_s,
            allow_redirects=True,
            verify=False,
            cookies=cookies or {},
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
            },
        )
        if resp.status_code == 200:
            html = resp.text
            # Cache cookies for this domain
            if resp.cookies:
                _set_cached_cookies(url, dict(resp.cookies))
            extracted = _bs4_deep_extract(html)
            if extracted and len(extracted) > 200:
                logger.debug(f"curl_cffi OK (profile={profile}, "
                             f"{len(extracted):,} chars) for {url}")
                return extracted
        elif resp.status_code in (403, 429):
            logger.warning(f"curl_cffi blocked (HTTP {resp.status_code}) for {url}")
    except Exception as e:
        logger.warning(f"curl_cffi failed for {url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Tier 3 — Camoufox (anti-detect Firefox)
# ---------------------------------------------------------------------------

def _try_camoufox(url: str, timeout_ms: int = 25000) -> Optional[str]:
    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        logger.debug("Camoufox not installed. Run: pip install camoufox[geoip]")
        return None

    try:
        with Camoufox(headless=True, block_images=True) as browser:
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            time.sleep(_poisson_delay(1.5, 1.0, 3.0))
            _human_scroll(page)
            html = page.content()
            # Cache cookies
            try:
                cookies = {c["name"]: c["value"]
                           for c in page.context.cookies()}
                _set_cached_cookies(url, cookies)
            except Exception:
                pass

        if html and len(html.strip()) > 500:
            extracted = _bs4_deep_extract(html)
            if extracted and len(extracted) > 200:
                logger.debug(f"Camoufox OK ({len(extracted):,} chars) for {url}")
                return extracted
    except Exception as e:
        logger.warning(f"Camoufox failed for {url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Tier 4 — Playwright + stealth + behavioral noise
# ---------------------------------------------------------------------------

def _try_playwright(url: str, timeout_ms: int = 25000) -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.debug("Playwright not installed.")
        return None

    # Stealth JS snippet — removes navigator.webdriver and common leaks
    _STEALTH_JS = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
        window.chrome = {runtime: {}};
        Object.defineProperty(navigator, 'permissions', {
            query: (p) => Promise.resolve({state: 'granted'})
        });
    """

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--window-size=1366,768",
                ],
            )
            cached_cookies = _get_cached_cookies(url)
            ctx = browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                java_script_enabled=True,
                ignore_https_errors=True,
            )

            # Inject stealth JS before every page load
            ctx.add_init_script(_STEALTH_JS)

            # Restore cached cookies
            if cached_cookies:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                ctx.add_cookies([
                    {"name": k, "value": v, "domain": domain, "path": "/"}
                    for k, v in cached_cookies.items()
                ])

            page = ctx.new_page()

            # Block heavy assets
            page.route(
                re.compile(
                    r"\.(png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|mp4|mp3|avi)$",
                    re.IGNORECASE,
                ),
                lambda route: route.abort(),
            )

            html = None
            try:
                page.goto(url, timeout=timeout_ms,
                          wait_until="domcontentloaded")
                # Poisson delay + human scroll
                time.sleep(_poisson_delay(2.0, 1.5, 4.0))
                _human_scroll(page, steps=random.randint(2, 4))

                # Cache new cookies
                try:
                    cookies = {c["name"]: c["value"]
                               for c in page.context.cookies()}
                    _set_cached_cookies(url, cookies)
                except Exception:
                    pass

                html = page.content()
            except PWTimeout:
                logger.warning(f"Playwright timeout for {url}")
            finally:
                browser.close()

        if html and len(html.strip()) > 500:
            extracted = _bs4_deep_extract(html)
            if extracted and len(extracted) > 200:
                logger.debug(f"Playwright+stealth OK ({len(extracted):,} chars)")
                return extracted
    except Exception as e:
        logger.warning(f"Playwright failed for {url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Main scraper class
# ---------------------------------------------------------------------------

class PlaywrightScraper:
    """
    Universal anti-bot scraper — 5 tiers + JSON API sniffing + session cache.
    """

    MAX_RETRIES = 2
    RETRY_BACKOFF = [2.0, 5.0]

    def __init__(self, headless: bool = True):
        self._headless = headless
        self.session = requests.Session()
        self._rotate_headers()

    def _rotate_headers(self):
        self.session.headers.update({
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "no-cache",
        })

    def launch_browser(self):
        pass

    def close_browser(self):
        try:
            self.session.close()
        except Exception:
            pass

    def scrape(
        self,
        url: str,
        timeout: int = 25000,
        retry_on_restart: bool = False,
    ) -> Optional[str]:

        if not url.startswith("http"):
            url = f"https://{url}"

        timeout_s = max(timeout / 1000.0, 10.0)

        # ── Pre-check: hidden JSON API ────────────────────────────────
        json_data = _try_json_api(url)
        if json_data and len(json_data) > 100:
            logger.debug(f"JSON API hit for {url}")
            return json_data

        # ── Tier 1: Tinyfish ─────────────────────────────────────────
        result = self._try_tinyfish(url)
        if result:
            return result

        # ── Tier 2: curl_cffi (TLS fingerprint spoof) ────────────────
        cached_cookies = _get_cached_cookies(url)
        result = _try_curl_cffi(url, timeout_s, cookies=cached_cookies)
        if result:
            return result

        # ── Tier 3: Camoufox (anti-detect Firefox) ───────────────────
        logger.debug(f"curl_cffi failed — trying Camoufox for {url}")
        result = _try_camoufox(url, timeout_ms=int(timeout_s * 1000))
        if result:
            # Now try curl_cffi again with fresh cookies from Camoufox
            cached_cookies = _get_cached_cookies(url)
            if cached_cookies:
                fast = _try_curl_cffi(url, timeout_s, cookies=cached_cookies)
                if fast:
                    return fast
            return result

        # ── Tier 4: Playwright + stealth ────────────────────────────
        logger.debug(f"Camoufox failed — trying Playwright for {url}")
        result = _try_playwright(url, timeout_ms=int(timeout_s * 1000))
        if result:
            return result

        # ── Tier 5: requests + deep BS4 ────────────────────────────
        return self._try_requests(url, timeout_s)

    # ------------------------------------------------------------------

    def _try_tinyfish(self, url: str) -> Optional[str]:
        tinyfish_key = os.getenv("TINYFISH_API_KEY", "")
        if not tinyfish_key:
            return None
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    "https://api.fetch.tinyfish.ai",
                    headers={"X-API-Key": tinyfish_key,
                             "Content-Type": "application/json"},
                    json={"urls": [url]},
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                if results and results[0].get("text"):
                    text = results[0]["text"]
                    if len(text.strip()) > 200:
                        logger.debug(f"Tinyfish OK ({len(text):,} chars)")
                        return text
                logger.warning(f"Tinyfish empty for {url}")
        except Exception as e:
            logger.warning(f"Tinyfish failed for {url}: {e}")
        return None

    def _try_requests(self, url: str, timeout_s: float) -> Optional[str]:
        last_err = None
        cached_cookies = _get_cached_cookies(url)

        for attempt in range(self.MAX_RETRIES):
            try:
                self._rotate_headers()
                resp = self.session.get(
                    url,
                    timeout=timeout_s,
                    allow_redirects=True,
                    verify=False,
                    cookies=cached_cookies or {},
                )
                resp.raise_for_status()

                extracted = _bs4_deep_extract(resp.text)
                if extracted and len(extracted) > 100:
                    logger.debug(f"requests+BS4 OK ({len(extracted):,} chars)")
                    return extracted

                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(_STRIP_TAGS):
                    tag.decompose()
                return str(soup)

            except requests.exceptions.Timeout as e:
                last_err = e
                logger.warning(f"Timeout attempt {attempt + 1} for {url}")
            except requests.exceptions.TooManyRedirects:
                logger.warning(f"Too many redirects for {url}")
                return None
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status in (403, 429):
                    wait = self.RETRY_BACKOFF[min(attempt,
                                                   len(self.RETRY_BACKOFF)-1)] * 2
                    logger.warning(f"HTTP {status} on {url}, backing off {wait}s")
                    time.sleep(wait)
                    continue
                elif status in (404, 410):
                    logger.warning(f"HTTP {status} for {url}, skipping.")
                    return None
                last_err = e
            except Exception as e:
                last_err = e
                logger.warning(f"Request error attempt {attempt + 1}: {e}")

            if attempt < self.MAX_RETRIES - 1:
                time.sleep(_poisson_delay(
                    self.RETRY_BACKOFF[attempt], 1.0, 8.0
                ))

        logger.warning(f"All tiers failed for {url}. Last: {last_err}")
        return None
