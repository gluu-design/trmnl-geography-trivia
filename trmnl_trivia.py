import os
import json
import re
from datetime import datetime
import requests
from google import genai

def main():
    # 1. Determine time state (Evening reveal vs Morning question)
    current_hour = datetime.now().hour
    show_answer = current_hour >= 18 or current_hour < 4

    # 2. Retrieve environment variables
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    webhook_url = os.getenv("TRMNL_WEBHOOK_URL")

    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY secret in GitHub settings.")
    if not webhook_url:
        raise ValueError("Missing TRMNL_WEBHOOK_URL secret in GitHub settings.")

    # 3. Initialize native Google Gen AI client
    client = genai.Client(api_key=api_key)

    prompt = (
        "Generate a fun geography trivia question based on an interesting or unusual statistic about a specific country or city.\n"
        "Respond ONLY with a valid, raw JSON object (no markdown, no ```json wrapper) with this exact schema:\n"
        "{\n"
        '  "country": "Name of Country or City",\n'
        '  "stat_category": "Short Category Label (e.g. Population Density)",\n'
        '  "question": "The question text",\n'
        '  "answer": "The concise answer",\n'
        '  "fun_fact": "A 1-sentence follow-up fun fact"\n'
        "}"
    )

    # 4. Generate content
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )

    # 5. Extract and parse JSON
    text_content = response.text.strip()
    match = re.search(r"\{.*\}", text_content, re.DOTALL)
    if match:
        json_str = match.group(0)
    else:
        json_str = text_content

    trivia_data = json.loads(json_str)

    # 6. Build TRMNL Payload
    payload = {
        "date": datetime.now().strftime("%B %d, %Y"),
        "country": trivia_data.get("country", "World Geography"),
        "stat_category": trivia_data.get("stat_category", "Fun Stat"),
        "question": trivia_data.get("question", "Question unavailable"),
        "answer": trivia_data.get("answer", "Answer unavailable"),
        "fun_fact": trivia_data.get("fun_fact", ""),
        "show_answer": show_answer
    }

    # 7. Post to TRMNL
    res = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"TRMNL Webhook Status Code: {res.status_code}")
    print(f"TRMNL Response Output: {res.text}")

if __name__ == "__main__":
    main()
