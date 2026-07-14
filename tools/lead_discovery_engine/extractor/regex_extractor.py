import re
from typing import List

# Known file extensions that are never email addresses
_FAKE_EMAIL_EXTENSIONS = re.compile(
    r"\.(png|jpg|jpeg|gif|svg|webp|ico|css|js|ts|tsx|jsx|woff|woff2|ttf|eot|pdf|zip|mp4|mov|avi|webm)$",
    re.IGNORECASE,
)

# Known throwaway / generic addresses that pollute results
_THROWAWAY_PREFIXES = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "webmaster", "hostmaster",
    "bounce", "bounces", "unsubscribe", "listserv",
}


class RegexExtractor:
    """
    Extracts structured information using regular expressions.
    """

    # Stricter email pattern — requires proper TLD (2-6 chars), no dots at start/end
    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9](?:[A-Za-z0-9._%+\-]{0,63}[A-Za-z0-9])?@"
        r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,253}[A-Za-z0-9])?\.[A-Za-z]{2,6}\b"
    )

    PHONE_PATTERN = re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{4,6}"
    )

    def extract_emails(self, text: str) -> List[str]:
        emails = self.EMAIL_PATTERN.findall(text)
        cleaned: list[str] = []
        seen: set[str] = set()
        for email in emails:
            lower = email.lower()
            # Drop fake/file emails
            if _FAKE_EMAIL_EXTENSIONS.search(lower):
                continue
            # Drop throwaway addresses
            local_part = lower.split("@")[0]
            if local_part in _THROWAWAY_PREFIXES:
                continue
            # Deduplicate case-insensitively
            if lower in seen:
                continue
            seen.add(lower)
            cleaned.append(email)
        return cleaned

    def extract_phones(self, text: str) -> List[str]:
        phones = self.PHONE_PATTERN.findall(text)
        cleaned = []
        seen: set[str] = set()
        for phone in phones:
            phone = phone.strip()
            if len(phone) >= 8:
                key = re.sub(r"\D", "", phone)  # digits only for dedup
                if key not in seen:
                    seen.add(key)
                    cleaned.append(phone)
        return cleaned