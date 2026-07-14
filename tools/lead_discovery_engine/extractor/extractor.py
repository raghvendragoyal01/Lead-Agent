from tools.lead_discovery_engine.extractor.providers.gemini_extractor import GeminiExtractor
from tools.lead_discovery_engine.extractor.regex_extractor import RegexExtractor
from tools.lead_discovery_engine.schemas.lead_schema import Contact, Lead


class Extractor:
    """
    Combines Regex extraction and AI extraction
    into a single validated Lead object.
    """

    def __init__(self):

        self.regex = RegexExtractor()
        self.ai = GeminiExtractor()

    def extract(
        self,
        text: str,
        website: str,
    ) -> Lead:

        lead = self.ai.extract(
            text=text,
            website=website,
        )

        # ── 1. Clean AI-extracted contacts ───────────────────────────
        cleaned_contacts = []
        for contact in lead.contacts:
            if contact.name or contact.designation or contact.email or contact.phone:
                cleaned_contacts.append(contact)
        lead.contacts = cleaned_contacts

        # ── 2. Collect emails/phones already present from AI pass ─────
        existing_emails = {
            str(c.email).lower()
            for c in lead.contacts
            if c.email
        }
        existing_phones = {
            c.phone.strip()
            for c in lead.contacts
            if c.phone
        }

        # ── 3. Append regex-found emails only if genuinely new ────────
        for email in self.regex.extract_emails(text)[:10]:
            if email.lower() not in existing_emails:
                lead.contacts.append(Contact(email=email))
                existing_emails.add(email.lower())

        for phone in self.regex.extract_phones(text)[:5]:
            if phone.strip() not in existing_phones:
                lead.contacts.append(Contact(phone=phone))
                existing_phones.add(phone.strip())

        return lead
