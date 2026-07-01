import google.generativeai as genai

from app.config.settings import settings


def main():

    print("API Key Loaded:", settings.GEMINI_API_KEY is not None)

    genai.configure(api_key=settings.GEMINI_API_KEY)

    model = genai.GenerativeModel("gemini-2.5-flash")

    response = model.generate_content(
        "Reply with exactly: Gemini Connected Successfully"
    )

    print(response.text)


if __name__ == "__main__":
    main()