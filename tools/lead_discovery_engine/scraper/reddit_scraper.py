"""
reddit_scraper.py
-----------------
Finds qualified leads from Reddit using PRAW (official Reddit API).

Strategy:
  1. Search relevant subreddits for posts matching the target niche
  2. Extract post authors + commenters who mention business/contact info
  3. Visit their public Reddit profiles to find any posted email/website
  4. Return structured lead dicts

Requires env vars:
  REDDIT_CLIENT_ID
  REDDIT_CLIENT_SECRET
  REDDIT_USER_AGENT   (optional, defaults to a safe value)

Get free credentials at: https://www.reddit.com/prefs/apps
Create a "script" type app — no review needed for read-only access.
"""

from __future__ import annotations

import os
import re
import time
from typing import Optional

from tools.lead_discovery_engine.extractor.regex_extractor import RegexExtractor
from tools.lead_discovery_engine.utils.logger import get_logger

logger = get_logger(__name__)
regex = RegexExtractor()

# Subreddits that tend to have business owners / professionals
_DEFAULT_SUBREDDITS = [
    "entrepreneur", "smallbusiness", "startups", "forhire",
    "hiring", "business", "digitalnomad", "freelance",
    "india", "indianstartups", "indiabusiness",
]

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9](?:[A-Za-z0-9._%+\-]{0,63}[A-Za-z0-9])?@"
    r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,253}[A-Za-z0-9])?\.[A-Za-z]{2,6}\b"
)

_URL_RE = re.compile(r"https?://[^\s)\]\"'>]+")

_THROWAWAY = {
    "noreply", "no-reply", "donotreply", "bounce", "mailer-daemon",
    "postmaster", "webmaster",
}


def _clean_email(email: str) -> Optional[str]:
    local = email.split("@")[0].lower()
    if local in _THROWAWAY:
        return None
    return email


def _extract_from_text(text: str) -> dict:
    """Pull emails, URLs, phone numbers from a block of text."""
    emails = [e for e in regex.extract_emails(text) if _clean_email(e)]
    phones = regex.extract_phones(text)
    urls = [u.rstrip(".,)") for u in _URL_RE.findall(text)
            if not any(s in u for s in ("reddit.com", "redd.it", "imgur.com"))]
    return {"emails": emails[:3], "phones": phones[:2], "urls": urls[:3]}


class RedditLeadScraper:
    """
    Extracts leads from Reddit posts and user profiles.
    """

    def __init__(self):
        self._praw = None

    def _get_reddit(self):
        if self._praw:
            return self._praw
        try:
            import praw
            client_id     = os.getenv("REDDIT_CLIENT_ID", "")
            client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
            user_agent    = os.getenv("REDDIT_USER_AGENT",
                                      "LeadEngine/1.0 by RGTVetrex")
            if not client_id or not client_secret:
                logger.warning("[Reddit] REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set. Skipping Reddit.")
                return None
            self._praw = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            logger.info("[Reddit] PRAW client initialised (read-only).")
            return self._praw
        except ImportError:
            logger.warning("[Reddit] praw not installed. Run: pip install praw")
            return None
        except Exception as e:
            logger.warning(f"[Reddit] PRAW init failed: {e}")
            return None

    def _profile_contact(self, reddit, username: str) -> dict:
        """Try to get contact info from a user's profile About/Description."""
        try:
            user = reddit.redditor(username)
            about = (getattr(user, "subreddit", {}) or {})
            desc = about.get("public_description", "") or ""
            if not desc:
                return {}
            return _extract_from_text(desc)
        except Exception:
            return {}

    def search_leads(
        self,
        query: str,
        location: str = "",
        max_leads: int = 20,
        subreddits: list[str] | None = None,
    ) -> list[dict]:
        """
        Search Reddit for posts matching the query and extract contact leads.

        Returns a list of lead dicts compatible with the pipeline schema.
        """
        reddit = self._get_reddit()
        if not reddit:
            return []

        target_subreddits = subreddits or _DEFAULT_SUBREDDITS
        search_query = f"{query} {location}".strip()
        leads: list[dict] = []
        seen_users: set[str] = set()
        seen_emails: set[str] = set()

        for sub_name in target_subreddits:
            if len(leads) >= max_leads:
                break
            try:
                sub = reddit.subreddit(sub_name)
                for post in sub.search(search_query, sort="relevance",
                                       time_filter="year", limit=15):
                    if len(leads) >= max_leads:
                        break

                    author = str(post.author or "")
                    if not author or author == "AutoModerator":
                        continue

                    # Extract from post title + body
                    combined = f"{post.title}\n{post.selftext}"
                    extracted = _extract_from_text(combined)

                    # Also check author's profile
                    if author not in seen_users:
                        seen_users.add(author)
                        profile_data = self._profile_contact(reddit, author)
                        extracted["emails"] = list(dict.fromkeys(
                            extracted["emails"] + profile_data.get("emails", [])
                        ))
                        extracted["phones"] = list(dict.fromkeys(
                            extracted["phones"] + profile_data.get("phones", [])
                        ))
                        extracted["urls"] = list(dict.fromkeys(
                            extracted["urls"] + profile_data.get("urls", [])
                        ))

                    email = extracted["emails"][0] if extracted["emails"] else None
                    phone = extracted["phones"][0] if extracted["phones"] else None
                    website = extracted["urls"][0] if extracted["urls"] else None

                    if not email and not phone:
                        continue
                    if email and email.lower() in seen_emails:
                        continue
                    if email:
                        seen_emails.add(email.lower())

                    leads.append({
                        "full_name": author,
                        "job_title": "Reddit User",
                        "email": email,
                        "phone": phone,
                        "company_name": website or f"reddit.com/u/{author}",
                        "industry": query,
                        "source": f"reddit/r/{sub_name}",
                        "post_title": post.title[:100],
                        "confidence_score": 0.7 if email else 0.4,
                    })

                    time.sleep(0.5)  # respect Reddit rate limits

            except Exception as e:
                logger.warning(f"[Reddit] Error scraping r/{sub_name}: {e}")
                continue

        logger.info(f"[Reddit] Found {len(leads)} leads for query '{search_query}'")
        return leads
