import time
import concurrent.futures
from typing import Dict, Any
from urllib.parse import urlparse

from agents.schemas import CampaignState
from tools.lead_discovery_engine.pipeline.pipeline import LeadDiscoveryPipeline

# Domains that are search/social/news aggregators — never actual company homepages
_BLOCKLIST_DOMAINS = {
    "wikipedia.org", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "tiktok.com", "youtube.com", "reddit.com",
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com",
    "topuniversities.com", "usnews.com", "timeshighereducation.com",
    "shanghairanking.com", "mastersportal.com", "studyportals.com",
    "careers360.com", "shiksha.com", "collegedunia.com",
    "qs.com", "the.com", "ranking.com",
    "forbes.com", "businessinsider.com", "techcrunch.com", "crunchbase.com",
    "bloomberg.com", "reuters.com", "cnn.com", "bbc.com", "theguardian.com",
    "medium.com", "substack.com", "quora.com", "stackoverflow.com",
    "github.com", "gitlab.com", "bitbucket.org",
    "amazon.com", "ebay.com", "etsy.com",
    "maps.google.com", "news.google.com",
    "ceoworld.biz", "inquirer.net", "clarivate.com",
    # Indian directories / news that return listing pages not company sites
    "yourstory.com", "justdial.com", "indiamart.com", "tradeindia.com",
    "sulekha.com", "yellowpages.in", "shiksha.com", "collegedunia.com",
    "careers360.com", "practo.com", "zomato.com", "swiggy.com",
    "smergers.com", "startupindia.gov.in", "istart.rajasthan.gov.in",
}


def _root_domain(url: str) -> str:
    """Return the registrable root domain (e.g. 'acme.com') for deduplication."""
    try:
        netloc = urlparse(url).netloc.lower()
        # Strip port
        netloc = netloc.split(":")[0]
        # Strip www. and common subdomains
        parts = netloc.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return netloc
    except Exception:
        return url


def lead_discoverer_node(state: CampaignState) -> Dict[str, Any]:
    target = state.get("target_criteria", "")
    location = state.get("location", None)
    niche = state.get("niche", None)
    platforms = state.get("platforms", None)
    max_leads = state.get("max_leads_per_day", 100)

    print(f"[Lead Discoverer] Searching for: {target} | Location: {location} | Niche: {niche} | Platforms: {platforms}")

    target_urls = []

    if target and target.startswith("http"):
        target_urls.append(target)
    else:
        print("[Lead Discoverer] Expanding search queries using LLM...")
        from config.llm_config import get_llm
        from pydantic import BaseModel, Field
        from typing import List
        from langchain_core.output_parsers import PydanticOutputParser
        from langchain_core.prompts import PromptTemplate

        class QueryExpansion(BaseModel):
            queries: List[str] = Field(description="A list of 3-5 highly optimized search queries to find company websites in the target niche and location. Include terms like 'startups', 'companies', 'incubators', 'accelerators', 'university spinoffs'.")

        llm = get_llm(temperature=0.7)
        parser = PydanticOutputParser(pydantic_object=QueryExpansion)

        prompt_template = PromptTemplate(
            template="""Generate 3-5 search engine queries to find '{target}' in '{location}'.
Your goal is to find their OFFICIAL WEBSITES so we can extract contact emails from them.

IMPORTANT RULES:
- The queries must be DIRECTLY about the target: '{target}'
- Do NOT change or reinterpret the target. If target is 'schools', search for schools. If target is 'restaurants', search for restaurants.
- Include the location '{location}' in every query
- Add terms like 'official website', 'contact', 'directory' to find real company sites
- Do NOT add B2B, startup, incubator framing unless the target itself mentions it

{format_instructions}""",
            input_variables=["target", "location"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        chain = prompt_template | llm | parser

        try:
            expansion = chain.invoke({
                "target": niche if niche else target,
                "location": location if location else "any location"
            })
            expanded_queries = expansion.queries
        except Exception as e:
            print(f"[Lead Discoverer] LLM Expansion failed: {e}. Falling back to basic query.")
            expanded_queries = [f"{niche if niche else target} in {location}" if location else f"{niche if niche else target}"]

        print(f"[Lead Discoverer] AI generated queries: {expanded_queries}")

        import httpx
        import urllib.parse
        from ddgs import DDGS
        import os

        tinyfish_key = os.getenv("TINYFISH_API_KEY", "")

        for q in expanded_queries:
            if platforms:
                q += f" site:{platforms[0]}.com"

            query_success = False
            print(f"[Lead Discoverer] Searching Tinyfish API for: {q}")
            try:
                encoded_q = urllib.parse.quote(q)
                url = f"https://api.search.tinyfish.ai?query={encoded_q}"
                headers = {"X-API-Key": tinyfish_key}

                with httpx.Client(timeout=30) as client:
                    resp = client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        for res in results:
                            if "url" in res:
                                target_urls.append(res["url"])
                        query_success = True
                    else:
                        print(f"[Lead Discoverer] Tinyfish returned 0 results for '{q}'")
            except Exception as e:
                print(f"[Lead Discoverer] Tinyfish search failed for query '{q}': {e}")

            if not query_success:
                print(f"[Lead Discoverer] Fallback: Searching DDG for: {q}")
                try:
                    ddgs = DDGS()
                    results = ddgs.text(q, max_results=15)
                    for res in results:
                        target_urls.append(res["href"])
                except Exception as e:
                    print(f"[Lead Discoverer] DDG Search failed for query '{q}': {e}")

        # ── Deduplicate by ROOT DOMAIN, not raw URL ──────────────────
        # This prevents processing acme.com, acme.com/about, acme.com/contact
        # as three separate "companies".
        seen_domains: dict[str, str] = {}
        for u in target_urls:
            domain = _root_domain(u)
            # Skip known non-company domains (aggregators, social, news, ranking sites)
            if any(blocked in domain for blocked in _BLOCKLIST_DOMAINS):
                print(f"[Lead Discoverer] Skipping non-company domain: {domain}")
                continue
            if domain not in seen_domains:
                seen_domains[domain] = u  # keep only the first (usually homepage) URL per domain

        target_urls = list(seen_domains.values())
        print(f"[Lead Discoverer] {len(target_urls)} unique company domains after deduplication.")

    # ── Also pull leads from Reddit and Quora ────────────────────────
    social_leads: list[dict] = []
    search_term = niche if niche else target
    loc = location if location else ""

    try:
        from tools.lead_discovery_engine.scraper.reddit_scraper import RedditLeadScraper
        reddit_scraper = RedditLeadScraper()
        r_leads = reddit_scraper.search_leads(
            query=search_term, location=loc, max_leads=max(5, max_leads // 4)
        )
        social_leads.extend(r_leads)
        print(f"[Lead Discoverer] Reddit: {len(r_leads)} leads found.")
    except Exception as e:
        print(f"[Lead Discoverer] Reddit scraper skipped: {e}")

    try:
        from tools.lead_discovery_engine.scraper.quora_scraper import QuoraLeadScraper
        quora_scraper = QuoraLeadScraper()
        q_leads = quora_scraper.search_leads(
            query=search_term, location=loc, max_leads=max(5, max_leads // 4)
        )
        social_leads.extend(q_leads)
        print(f"[Lead Discoverer] Quora: {len(q_leads)} leads found.")
    except Exception as e:
        print(f"[Lead Discoverer] Quora scraper skipped: {e}")

    try:
        from tools.lead_discovery_engine.scraper.google_dork_scraper import GoogleDorkScraper
        dork_scraper = GoogleDorkScraper()
        d_leads = dork_scraper.search_leads(
            target=search_term, location=loc, max_leads=max(10, max_leads // 3)
        )
        social_leads.extend(d_leads)
        print(f"[Lead Discoverer] Google Dork: {len(d_leads)} leads found.")
    except Exception as e:
        print(f"[Lead Discoverer] Google Dork scraper skipped: {e}")

    extracted_leads = []
    # Track processed companies by root domain so we never count the same
    # company twice even if search returns multiple pages from it.
    processed_domains: set[str] = set()

    # ── Multi-threaded pipeline: 3 workers for parallel site scraping ─
    MAX_WORKERS = 3
    INTER_SITE_DELAY = 1.0  # seconds between starting each site scrape

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

            # Each worker gets its own pipeline instance (not thread-safe to share)
            pipeline_pool: dict[int, LeadDiscoveryPipeline] = {}

            def get_pipeline() -> LeadDiscoveryPipeline:
                import threading
                tid = threading.get_ident()
                if tid not in pipeline_pool:
                    pipeline_pool[tid] = LeadDiscoveryPipeline()
                return pipeline_pool[tid]

            def process_url(url: str) -> dict | None:
                """Run the pipeline for one URL; returns lead_data dict or None."""
                try:
                    pipeline = get_pipeline()
                    lead_obj = pipeline.run(homepage_url=url)
                    return lead_obj.model_dump(mode="json")
                except Exception as e:
                    print(f"[Lead Discoverer] Skipped {url} due to error: {e}")
                    return None

            # Submit all URLs but throttle start time slightly to avoid slamming
            # multiple sites simultaneously at t=0.
            future_to_url: dict[concurrent.futures.Future, str] = {}
            for i, url in enumerate(target_urls):
                if len(extracted_leads) >= max_leads:
                    break
                if i > 0:
                    time.sleep(INTER_SITE_DELAY)
                future = executor.submit(process_url, url)
                future_to_url[future] = url

            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                domain = _root_domain(url)

                if len(extracted_leads) >= max_leads:
                    future.cancel()
                    continue

                # Skip if we already got leads from this domain
                if domain in processed_domains:
                    print(f"[Lead Discoverer] Skipped duplicate domain: {domain}")
                    continue

                lead_data = future.result()
                if not lead_data:
                    continue

                company_name = lead_data.get("company_name", url)
                processed_domains.add(domain)

                contacts = lead_data.get("contacts", [])
                if not contacts:
                    print(f"[Lead Discoverer] No contacts extracted for {company_name}.")
                    continue

                # Pick best contact per company — named person beats generic email
                def _contact_priority(c: dict) -> int:
                    score = 0
                    name = (c.get("name") or "").lower()
                    if name and name not in ("team", "contact", "unknown", "none", ""):
                        score += 4
                    if c.get("designation"):
                        score += 2
                    email = c.get("email") or ""
                    local = email.split("@")[0].lower() if "@" in email else ""
                    _generic = {"info","contact","hello","admin","support","sales",
                                "mail","office","enquiry","inquiry","team","hr"}
                    if email and local not in _generic:
                        score += 3
                    elif email:
                        score += 1
                    if c.get("phone"):
                        score += 1
                    return score

                # Sort contacts by quality and take only ONE per company
                valid_contacts = [c for c in contacts if c.get("email")]
                valid_contacts.sort(key=_contact_priority, reverse=True)
                best_contact = valid_contacts[0] if valid_contacts else None

                if not best_contact:
                    print(f"[Lead Discoverer] No contacts with email for {company_name}.")
                    continue

                if len(extracted_leads) >= max_leads:
                    break

                email = best_contact.get("email")

                # Validate email format
                try:
                    from email_validator import validate_email, EmailNotValidError
                    validate_email(email, check_deliverability=False)
                except EmailNotValidError:
                    print(f"[Lead Discoverer] Skipped invalid email: {email}")
                    continue

                # Deduplicate against Neo4j database
                try:
                    from memory.neo4j_client import Neo4jMemoryClient
                    neo4j = Neo4jMemoryClient()
                    _, dups = neo4j.filter_new_leads([{"email": email, "company_name": company_name}])
                    if dups:
                        print(f"[Lead Discoverer] Skipped duplicate lead: {email}")
                        continue
                except Exception:
                    pass

                raw_name = best_contact.get("name")
                full_name = raw_name if raw_name and str(raw_name).lower() not in ["none", "unknown", "null", ""] else "Team"

                raw_job = best_contact.get("designation")
                job_title = raw_job if raw_job and str(raw_job).lower() not in ["none", "unknown", "null", ""] else "Contact"

                extracted_leads.append({
                    "full_name": full_name,
                    "job_title": job_title,
                    "email": email,
                    "phone": best_contact.get("phone"),
                    "company_name": company_name,
                    "industry": lead_data.get("industry", niche),
                    "confidence_score": 0.9,
                })

    except Exception as e:
        print(f"[Lead Discoverer] Pipeline initialization failed: {e}")

    print(f"[Lead Discoverer] Extraction complete. {len(extracted_leads)} leads found.")

    # Merge social leads (Reddit/Quora) — deduplicate by email
    existing_emails = {l["email"].lower() for l in extracted_leads if l.get("email")}
    for lead in social_leads:
        if len(extracted_leads) >= max_leads:
            break
        email = (lead.get("email") or "").lower()
        if email and email in existing_emails:
            continue
        if email:
            existing_emails.add(email)
        extracted_leads.append(lead)

    print(f"[Lead Discoverer] Total leads after social merge: {len(extracted_leads)}")
    return {"raw_leads": extracted_leads, "current_status": "discovery_completed"}
