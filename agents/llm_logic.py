import json
import re
from langchain_core.prompts import ChatPromptTemplate
from agents.schemas import LeadExtractionResult
from config.llm_config import get_llm

llm = get_llm(temperature=0.1)

# DO NOT use with_structured_output — NVIDIA Llama doesn't support tool/function calling
# reliably and silently returns empty lists. Use manual JSON parsing instead.

extraction_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an elite B2B Lead Generation Agent. 
    Your job is to analyze raw text scraped from websites or search engines and extract precise lead information.
    
    CRITICAL RULES:
    1. Extract ONLY information present in the text. Do NOT hallucinate or guess emails.
    2. If a field is missing, leave it as 'Unknown' or null.
    3. Calculate a confidence_score based on how clear the data is (0.9 for clear contact pages, 0.4 for vague mentions).
    4. Provide a 1-2 sentence company_description summarizing what the company does based on the text.
    5. Return ONLY a valid JSON object with a "leads" array. No markdown, no explanation."""),
    ("human", "Here is the target criteria: {target_criteria}\n\nHere is the raw scraped text to analyze:\n{raw_html_text}\n\nReturn JSON matching: {{\"leads\": [{{\"full_name\": str, \"job_title\": str, \"company_name\": str, \"company_description\": str|null, \"email\": str|null, \"phone\": str|null, \"industry\": str|null, \"confidence_score\": float, \"draft_options\": [], \"final_draft\": null}}]}}")
])


def _parse_leads_json(response_text: str) -> list:
    """Parse LLM JSON response into a list of lead dicts."""
    response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
    response_text = response_text.replace("```json", "").replace("```", "").strip()
    response_text = re.sub(r',\s*([\]}])', r'\1', response_text)

    json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
    if json_match:
        response_text = json_match.group(1)

    data = json.loads(response_text)
    leads_raw = data.get("leads", [])

    cleaned = []
    for lead in leads_raw:
        # Sanitize obfuscated/placeholder emails before validation
        email = lead.get("email")
        if email:
            # Replace obfuscated patterns like [at], (at), [dot], (dot)
            email = re.sub(r'\s*[\[\(]at[\]\)]\s*', '@', email, flags=re.IGNORECASE)
            email = re.sub(r'\s*[\[\(]dot[\]\)]\s*', '.', email, flags=re.IGNORECASE)
            email = email.strip()
            # Drop if still not a real email
            if '@' not in email or '.' not in email.split('@')[-1]:
                email = None
        lead["email"] = email
        cleaned.append(lead)

    return cleaned


extraction_chain = extraction_prompt | llm


def extract_leads_from_text(raw_text: str, criteria: str) -> list:
    print("[LLM] Analyzing raw text and extracting structured JSON...")
    response = extraction_chain.invoke({
        "target_criteria": criteria,
        "raw_html_text": raw_text
    })
    try:
        return _parse_leads_json(response.content)
    except Exception as e:
        print(f"[LLM] extract_leads_from_text parse error: {e}")
        return []


qualifier_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a Data Quality Agent. Your ONLY job is to clean and standardize lead data.

RULES:
1. Standardize formatting (proper capitalization of names and companies).
2. Fix obfuscated emails: "name [at] company [dot] com" → "name@company.com".
3. If email has comma-separated values, keep only the first one.
4. KEEP ALL LEADS that have a valid email address — do not drop them for any other reason.
5. Only remove leads that have NO email AND NO phone at all.
6. Do NOT judge relevance to niche — keep everything with contact info.
7. Return ONLY valid JSON. No markdown, no explanation."""),
    ("human", "Target Criteria: {target_criteria}\n\nLeads to clean:\n{leads_json}\n\nReturn JSON: {{\"leads\": [{{\"full_name\": str, \"job_title\": str, \"company_name\": str, \"company_description\": str|null, \"email\": str|null, \"phone\": str|null, \"industry\": str|null, \"confidence_score\": float, \"draft_options\": [], \"final_draft\": null}}]}}")
])

qualifier_chain = qualifier_prompt | llm


def qualify_leads_with_llm(leads: list, criteria: str) -> list:
    print("[LLM] Standardizing and qualifying extracted leads...")
    if not leads:
        return []

    response = qualifier_chain.invoke({
        "target_criteria": criteria,
        "leads_json": json.dumps(leads, default=str)
    })

    try:
        result = _parse_leads_json(response.content)
        if not result:
            # LLM returned empty — return the input leads as-is rather than losing them
            print("[LLM] Qualifier returned empty list — returning input leads unchanged.")
            return leads
        return result
    except Exception as e:
        print(f"[LLM] qualify_leads_with_llm parse error: {e}. Returning input leads unchanged.")
        return leads