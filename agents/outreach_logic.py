import re
import json
import time
from typing import Dict, Any

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from agents.schemas import CampaignState
from config.llm_config import get_llm
from memory.campaign_store import CampaignStore
from memory.neo4j_client import Neo4jMemoryClient
from memory.qdrant_client import QdrantMemoryClient
from tools.email_sender import EmailSender


llm = get_llm(temperature=0.7)
qdrant_memory = QdrantMemoryClient()
neo4j_memory = Neo4jMemoryClient()
email_sender = EmailSender()
campaign_store = CampaignStore()


def retrieve_successful_templates(industry: str) -> str:
    return qdrant_memory.retrieve_successful_templates(industry)


email_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an elite B2B Outbound Sales Agent.
Write a professional, polite, value-driven cold email to the prospect.

CRITICAL RULES:
1. Tone: strictly professional and conversational. No aggressive sales language. No exclamation marks.
2. Personalize using their Name, Job Title, and Company.
3. Keep it under 100 words. No fluff.
4. End with a clear, low-friction question.
5. Do NOT include a sign-off or signature.
6. Return ONLY a JSON object with keys "subject" and "body". No markdown, no explanation.
""",
    ),
    (
        "human",
        """Prospect Details:
Name: {name}
Role: {role}
Company: {company}
Company Description: {company_description}

Context from Vector DB:
{rag_context}

Return JSON: {{"subject": "...", "body": "..."}}""",
    ),
])

email_chain = email_prompt | llm


def _parse_email_draft(response_text: str) -> dict:
    """Parse LLM JSON response into subject/body dict."""
    response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
    response_text = response_text.replace("```json", "").replace("```", "").strip()
    response_text = re.sub(r',\s*([\]}])', r'\1', response_text)
    json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
    if json_match:
        response_text = json_match.group(1)
    return json.loads(response_text)


def generate_draft_options(lead: dict) -> list[str]:
    industry = lead.get("industry") or "Technology"

    rag_context = retrieve_successful_templates(industry)
    options = []

    try:
        response = email_chain.invoke({
            "name": lead.get("full_name", "there"),
            "role": lead.get("job_title", "your role"),
            "company": lead.get("company_name", "your company"),
            "company_description": lead.get("company_description", "No description provided."),
            "rag_context": rag_context,
        })
        draft = _parse_email_draft(response.content)
        subject = draft.get("subject", "Following Up")
        body = draft.get("body", "")
        signature = "\n\nBest regards,\nCTO, Raghvendra Goyal"
        options.append(f"Subject: {subject}\n\n{body}{signature}")
    except Exception as e:
        print(f"[Drafter] Error drafting email for {lead.get('email')}: {e}")
        # Fallback plain draft so the lead isn't lost
        options.append(
            f"Subject: Quick question for {lead.get('company_name', 'your team')}\n\n"
            f"Hi {lead.get('full_name', 'there')},\n\n"
            f"I came across {lead.get('company_name', 'your company')} and wanted to reach out. "
            f"Would you be open to a quick 15-minute chat?\n\n"
            f"Best regards,\nCTO, Raghvendra Goyal"
        )

    return options

def drafter_node(state: CampaignState) -> Dict[str, Any]:
    print("[Drafter] Pre-generating email drafts before approval...")
    validated_leads = state.get("validated_leads", [])
    
    for lead in validated_leads:
        print(f"   -> Generating options for {lead.get('full_name')} at {lead.get('company_name')}...")
        options = generate_draft_options(lead)
        lead["draft_options"] = options
        
    return {"validated_leads": validated_leads}


def outreach_writer_node(state: CampaignState) -> Dict[str, Any]:
    print("[Outreach Writer] Sending approved emails...")

    sent_emails_log = []
    outreach_results = []
    followup_schedule = []
    thread_id = state.get("campaign_id", "unknown_campaign")

    for lead in state.get("approved_leads", []):
        print(f"   -> Sending finalized email to {lead.get('full_name')} at {lead.get('company_name')}...")

        final_draft = lead.get("final_draft")

        if not final_draft:
            print(f"   Skipping {lead.get('email')} because no final draft was provided.")
            outreach_results.append({
                "email": lead.get("email"),
                "status": "skipped",
                "message": "No final draft provided.",
            })
            continue

        # Parse subject and body from the finalized text
        lines = final_draft.split('\n')
        subject = "Hello"
        if lines[0].lower().startswith("subject:"):
            subject = lines[0].replace("Subject:", "", 1).strip()
            body = '\n'.join(lines[1:]).strip()
        else:
            body = final_draft.strip()

        try:
            send_result = email_sender.send_email(
                to_email=lead.get("email"),
                subject=subject,
                body=body,
            )
            print(f"   [+] Sent email to {lead.get('email')} (Subject: {subject})")
            
            status = send_result.get("status", "unknown")
            print(f"   [{status.upper()}] {lead.get('email')}: {send_result.get('message')}")

            if status in {"sent", "draft_only"}:
                sent_emails_log.append(lead.get("email"))

            outreach_record = campaign_store.log_outreach(
                thread_id=thread_id,
                campaign_id=thread_id,
                lead=lead,
                delivery_status=status,
                subject=subject,
                message_id=send_result.get("message_id"),
                delivery_message=send_result.get("message"),
            )

            if status == "sent":
                campaign_store.schedule_followups(
                    thread_id=thread_id,
                    campaign_id=thread_id,
                    leads=[lead],
                )
                followup_schedule.append(outreach_record["outreach_id"])

            neo4j_memory.create_lead_and_interaction(
                lead=lead,
                campaign_id=thread_id,
                interaction_type="EMAIL_SENT",
                metadata={"subject": subject, "status": status}
            )

            outreach_results.append({
                "email": lead.get("email"),
                "status": status,
                "message": send_result.get("message"),
            })
            
        except Exception as e:
            print(f"   [!] Failed to send to {lead.get('email')}: {e}")
            outreach_results.append({
                "email": lead.get("email"),
                "status": "failed",
                "message": str(e),
            })

        print("   [System] Waiting 2 seconds to respect rate limits...")
        time.sleep(2)

    metrics = campaign_store.get_metrics(thread_id=thread_id)
    state_snapshot = dict(state)
    
    # If there are still leads in validated_leads (the ones left behind), set status to awaiting_approval
    remaining = len(state.get("validated_leads", []))
    new_status = "awaiting_approval" if remaining > 0 else "campaign_finished"
    
    existing_sent = state.get("sent_emails", [])
    all_sent = existing_sent + sent_emails_log

    existing_results = state.get("outreach_results", [])
    all_results = existing_results + outreach_results

    existing_followups = state.get("followup_schedule", [])
    all_followups = existing_followups + followup_schedule

    state_snapshot.update({
        "sent_emails": all_sent,
        "outreach_results": all_results,
        "followup_schedule": all_followups,
        "metrics": metrics,
        "current_status": new_status,
        "approved_leads": [], # Clear approved leads so we don't send them again if the graph resumes
    })
    campaign_store.save_snapshot(thread_id, state_snapshot)

    return {
        "sent_emails": all_sent,
        "outreach_results": all_results,
        "followup_schedule": all_followups,
        "metrics": metrics,
        "current_status": new_status,
        "approved_leads": [],
    }
