import os
import json
import re
from datetime import datetime
import requests
from google import genai
from google.genai import types

def main():
    # 1. Determine local time state (Evening reveal vs Morning question)
    current_hour = datetime.now().hour
    show_answer = current_hour >= 18 or current_hour < 4

    # 2. Retrieve secrets from environment
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    webhook_url = os.getenv("TRMNL_WEBHOOK_URL")

    if not api_key:
        raise ValueError("CRITICAL ERROR: GEMINI_API_KEY secret is missing in GitHub settings.")
    if not webhook_url:
        raise ValueError("CRITICAL ERROR: TRMNL_WEBHOOK_URL secret is missing in GitHub settings.")

    # 3. Initialize Google GenAI client
    client = genai.Client(api_key=api_key)

    prompt = (
        "Generate a fun geography trivia question based on an interesting or unusual statistic about a specific country or city.\n"
        "Respond strictly with JSON containing these exact keys: country, stat_category, question, answer, fun_fact."
    )

    # 4. Request JSON response from Gemini 2.5 Flash
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8
        )
    )

    # 5. Parse JSON output
    trivia_data = json.loads(response.text)

    # 6. Construct payload for TRMNL
    payload = {
        "date": datetime.now().strftime("%B %d, %Y"),
        "country": trivia_data.get("country", "Geography Trivia"),
        "stat_category": trivia_data.get("stat_category", "Fun Stat"),
        "question": trivia_data.get("question", "Question unavailable"),
        "answer": trivia_data.get("answer", "Answer unavailable"),
        "fun_fact": trivia_data.get("fun_fact", ""),
        "show_answer": show_answer
    }

    # 7. Push payload to TRMNL Webhook
    res = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"TRMNL Response Code: {res.status_code}")
    print(f"TRMNL Response Body: {res.text}")

if __name__ == "__main__":
    main()
