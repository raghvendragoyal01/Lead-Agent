import json

import google.generativeai as genai

from app.config.settings import settings
from app.extractor.ai_extractor import AIExtractor
from app.prompts.lead_extraction_prompt import (
    build_lead_extraction_prompt,
)
from app.schemas.lead_schema import Lead


class GeminiExtractor(AIExtractor):
    """
    Gemini implementation of the AI-based lead extractor.
    """

    def __init__(self):

        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY not found. Please check your .env file."
            )

        genai.configure(api_key=settings.GEMINI_API_KEY)

        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash"
        )

    def extract(
        self,
        text: str,
        website: str,
    ) -> Lead:

        prompt = build_lead_extraction_prompt(text)

        try:

            response = self.model.generate_content(prompt)

            response_text = response.text.strip()

            # Remove markdown code blocks if Gemini returns them
            response_text = (
                response_text
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            data = json.loads(response_text)

            # Inject the known website before validation
            data["website"] = website

            return Lead.model_validate(data)

        except json.JSONDecodeError as e:

            raise ValueError(
                f"Gemini returned invalid JSON.\n\n{response_text}"
            ) from e

        except Exception as e:

            raise RuntimeError(
                f"Gemini extraction failed: {e}"
            ) from e