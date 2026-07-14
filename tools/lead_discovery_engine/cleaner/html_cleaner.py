"""
html_cleaner.py
---------------
Deep HTML cleaning using BeautifulSoup + trafilatura.

When the input is already clean text/markdown (from Tinyfish), the cleaner
detects this and skips the HTML parsing stage entirely.
"""

from __future__ import annotations

import re
from bs4 import BeautifulSoup, Comment, NavigableString

import trafilatura

# Tags to strip wholesale before text extraction
_NOISE_TAGS = {
    "script", "style", "noscript", "meta", "link", "svg", "canvas",
    "iframe", "object", "embed", "applet", "base",
    "figure", "picture", "source", "track",
    "button", "select",
}

# These structural tags add noise when rendered as text
_STRUCTURAL_NOISE = {"nav", "footer", "aside"}

# Attributes that often contain useful inline text
_USEFUL_ATTRS = ("alt", "title", "placeholder", "aria-label")


class HTMLCleaner:
    """
    Two-stage HTML → plain text pipeline:

    Stage 1 — BeautifulSoup deep clean:
      - Removes all noise tags
      - Promotes mailto/tel link text
      - Extracts alt text, aria-labels, title attributes
      - Removes HTML comments (except those with contact hints)
      - Normalises whitespace aggressively

    Stage 2 — trafilatura main-content extraction:
      - Strips boilerplate (ads, nav, footers)
      - Returns the highest-signal prose

    If the input looks like plain text/markdown already (from Tinyfish),
    skip both stages and return it directly.
    """

    # Heuristic: if < 10% of characters are '<', treat as plain text
    _HTML_THRESHOLD = 0.10

    def clean(self, html: str) -> str:
        if not html:
            return ""

        # ── Detect plain text / markdown ─────────────────────────────
        tag_ratio = html.count("<") / max(len(html), 1)
        if tag_ratio < self._HTML_THRESHOLD:
            # Already clean text — just normalise whitespace
            return self._normalise(html)

        # ── Stage 1: BeautifulSoup deep clean ────────────────────────
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise tags completely
        for tag in soup(_NOISE_TAGS):
            tag.decompose()

        # Remove structural chrome but keep their text if it contains signals
        for tag in soup(_STRUCTURAL_NOISE):
            text = tag.get_text(" ", strip=True).lower()
            if any(k in text for k in ("contact", "email", "@", "phone", "tel:")):
                # Promote the text as a plain string before removing the tag
                tag.replace_with(NavigableString(tag.get_text(" ", strip=True)))
            else:
                tag.decompose()

        # Promote mailto: and tel: links to visible text
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            if href.lower().startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if email:
                    a.replace_with(NavigableString(f" Email: {email} "))
            elif href.lower().startswith("tel:"):
                phone = href[4:].strip()
                if phone:
                    a.replace_with(NavigableString(f" Phone: {phone} "))

        # Promote useful attributes (alt, title, aria-label) to visible text
        for tag in soup.find_all(True):
            for attr in _USEFUL_ATTRS:
                val = tag.get(attr, "").strip()
                if val and len(val) > 3:
                    # Append as invisible NavigableString so trafilatura sees it
                    tag.append(NavigableString(f" {val} "))

        # Keep HTML comments only if they contain contact hints
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            text = comment.strip()
            if text and ("@" in text or any(
                k in text.lower() for k in ("email", "phone", "contact")
            )):
                comment.replace_with(NavigableString(f" {text} "))
            else:
                comment.extract()

        # Flatten tables: replace <td>/<th> boundaries with " | "
        for td in soup.find_all(["td", "th"]):
            td.append(NavigableString(" | "))

        cleaned_html = str(soup)

        # ── Stage 2: trafilatura main-content extraction ──────────────
        extracted = trafilatura.extract(
            cleaned_html,
            include_links=True,
            include_images=False,
            include_tables=True,
            no_fallback=False,
            deduplicate=True,
        )

        if extracted and len(extracted.strip()) > 100:
            return self._normalise(extracted)

        # Fallback: raw text from soup
        raw = soup.get_text(separator="\n", strip=True)
        return self._normalise(raw)

    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(text: str) -> str:
        """Collapse excess whitespace while preserving paragraph breaks."""
        # Collapse 3+ blank lines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Collapse multiple spaces/tabs on one line
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()
