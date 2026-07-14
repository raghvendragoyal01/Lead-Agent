"""
lead_validator.py
-----------------
Cleans and deduplicates extracted lead contacts.

Key rule: two contacts from the same company are treated as one lead —
we keep the one with the most information (named person > generic email).
"""

from __future__ import annotations

import re
from typing import Optional

from tools.lead_discovery_engine.schemas.lead_schema import Contact, Lead


def _email_domain(email: Optional[str]) -> str:
    """Return the domain part of an email, lower-cased."""
    if not email:
        return ""
    parts = str(email).split("@")
    return parts[-1].lower() if len(parts) == 2 else ""


def _is_generic(email: Optional[str]) -> bool:
    """True for info@, contact@, hello@, admin@ etc. — lower priority."""
    if not email:
        return True
    local = str(email).split("@")[0].lower()
    return local in {
        "info", "contact", "hello", "admin", "support", "sales",
        "mail", "office", "enquiry", "enquiries", "inquiry",
        "noreply", "no-reply", "team", "hr", "careers",
        "helpdesk", "help", "service", "services", "general",
    }


def _contact_score(c: Contact) -> int:
    """Higher = better contact to keep when merging duplicates."""
    score = 0
    if c.name and c.name.lower() not in ("team", "contact", "unknown", "none"):
        score += 4
    if c.designation:
        score += 2
    if c.email and not _is_generic(c.email):
        score += 3
    elif c.email:
        score += 1
    if c.phone:
        score += 1
    return score


class LeadValidator:
    """
    Cleans and validates extracted lead information.
    """

    def clean_contacts(self, lead: Lead) -> Lead:
        """
        Deduplicate contacts with two strategies:

        1. Exact dedup: same email or same phone → merge fields
        2. Domain dedup: multiple emails from the same company domain
           → keep the highest-scoring one (named person beats generic)
        """
        # ── Step 1: exact key dedup (same email or same phone) ───────
        exact: dict[str, Contact] = {}

        for contact in lead.contacts:
            key = str(contact.email or "").lower() or str(contact.phone or "") or str(contact.name or "")
            if not key:
                continue

            if key not in exact:
                exact[key] = contact
            else:
                existing = exact[key]
                # Merge missing fields into existing
                if not existing.name and contact.name:
                    existing.name = contact.name
                if not existing.designation and contact.designation:
                    existing.designation = contact.designation
                if not existing.email and contact.email:
                    existing.email = contact.email
                if not existing.phone and contact.phone:
                    existing.phone = contact.phone

        contacts = list(exact.values())

        # ── Step 2: domain dedup — same company, different emails ─────
        # Group by email domain.  For each domain keep the best contact;
        # merge name/designation from the others into it.
        domain_groups: dict[str, list[Contact]] = {}
        no_email: list[Contact] = []

        for c in contacts:
            domain = _email_domain(c.email)
            if domain:
                domain_groups.setdefault(domain, []).append(c)
            else:
                no_email.append(c)

        merged: list[Contact] = []
        for domain, group in domain_groups.items():
            if len(group) == 1:
                merged.append(group[0])
                continue

            # Sort by score descending — best contact first
            group.sort(key=_contact_score, reverse=True)
            best = group[0]

            # Absorb name/designation from runner-up if best is generic
            for other in group[1:]:
                if not best.name and other.name:
                    best.name = other.name
                if not best.designation and other.designation:
                    best.designation = other.designation
                if not best.phone and other.phone:
                    best.phone = other.phone

            merged.append(best)

        # Phone-only or name-only contacts that had no email
        merged.extend(no_email)

        lead.contacts = merged
        return lead

    def validate(self, lead: Lead, source_text: str) -> Lead:
        lead = self.clean_contacts(lead)
        return lead
