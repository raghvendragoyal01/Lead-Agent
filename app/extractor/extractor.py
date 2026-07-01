from app.extractor.providers.gemini_extractor import GeminiExtractor
from app.extractor.regex_extractor import RegexExtractor
from app.schemas.lead_schema import Contact, Lead


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

        # AI extraction
        lead = self.ai.extract(
            text=text,
            website=website,
        )

        # -----------------------------
        # Remove Empty Contacts
        # -----------------------------
        cleaned_contacts = []

        for contact in lead.contacts:

            if (
                contact.name
                or contact.designation
                or contact.email
                or contact.phone
            ):
                cleaned_contacts.append(contact)

        lead.contacts = cleaned_contacts

        # -----------------------------
        # Regex Extraction
        # -----------------------------
        emails = self.regex.extract_emails(text)
        phones = self.regex.extract_phones(text)

        if emails or phones:

            regex_contact = Contact(
                email=emails[0] if emails else None,
                phone=phones[0] if phones else None,
            )

            lead.contacts.append(regex_contact)

        return lead