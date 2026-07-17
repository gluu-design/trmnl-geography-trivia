import os
import json
import re
from datetime import datetime
import requests
from langchain_google_genai import ChatGoogleGenerativeAI

def extract_json(text: str) -> dict:
    """Safely extract JSON from raw model response."""
    # Clean markdown code blocks if present
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(text)

def main():
    # 1. Determine local time state (Morning vs Evening)
    current_hour = datetime.now().hour
    show_answer = current_hour >= 18 or current_hour < 4

    # 2. Get API keys
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    webhook_url = os.getenv("TRMNL_WEBHOOK_URL")

    if not api_key:
        raise ValueError("Error: GEMINI_API_KEY secret is missing or empty.")
    if not webhook_url:
        raise ValueError("Error: TRMNL_WEBHOOK_URL secret is missing or empty.")

    # 3. Initialize Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=api_key,
        temperature=0.8
    )

    prompt = (
        "Generate a fun geography trivia question based on an interesting or unusual statistic about a specific country or city.\n"
        "Respond ONLY with a valid, raw JSON object (no markdown, no extra conversational text) with this exact schema:\n"
        "{\n"
        '  "country": "Name of Country or City",\n'
        '  "stat_category": "Short Category Label (e.g. Population Density)",\n'
        '  "question": "The question text",\n'
        '  "answer": "The concise answer",\n'
        '  "fun_fact": "A 1-sentence follow-up fun fact"\n'
        "}"
    )

    # 4. Invoke model and parse JSON safely
    response = llm.invoke(prompt)
    raw_content = response.content if hasattr(response, 'content') else str(response)
    trivia_data = extract_json(raw_content)

    # 5. Build payload
    payload = {
        "date": datetime.now().strftime("%B %d, %Y"),
        "country": trivia_data.get("country", "Geography Trivia"),
        "stat_category": trivia_data.get("stat_category", "General"),
        "question": trivia_data.get("question", "Question missing."),
        "answer": trivia_data.get("answer", "Answer missing."),
        "fun_fact": trivia_data.get("fun_fact", ""),
        "show_answer": show_answer
    }

    # 6. Push to TRMNL Webhook
    res = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"TRMNL Webhook Status Code: {res.status_code}")
    print(f"TRMNL Response: {res.text}")

if __name__ == "__main__":
    main()
