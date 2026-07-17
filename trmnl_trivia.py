import os
import json
from datetime import datetime
import requests
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

def main():
    # Determine state: True after 6 PM (18:00) local time, False in the morning
    current_hour = datetime.now().hour
    show_answer = current_hour >= 18 or current_hour < 4

    # Connect to Google Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash", 
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.8
    )

    prompt = ChatPromptTemplate.from_template(
        "Generate a fun geography trivia question based on an interesting or unusual statistic about a specific country or city.\n"
        "Respond ONLY with a valid JSON object in this format:\n"
        "{{\n"
        '  "country": "Name of Country or City",\n'
        '  "stat_category": "Short Category Label (e.g., Population Density, Elevation)",\n'
        '  "question": "The question text",\n'
        '  "answer": "The concise answer",\n'
        '  "fun_fact": "A 1-sentence follow-up fun fact"\n'
        "}}"
    )

    chain = prompt | llm | JsonOutputParser()
    trivia_data = chain.invoke({})

    # Format payload for TRMNL
    payload = {
        "date": datetime.now().strftime("%B %d, %Y"),
        "country": trivia_data.get("country"),
        "stat_category": trivia_data.get("stat_category"),
        "question": trivia_data.get("question"),
        "answer": trivia_data.get("answer"),
        "fun_fact": trivia_data.get("fun_fact"),
        "show_answer": show_answer
    }

    # Post to TRMNL
    webhook_url = os.getenv("TRMNL_WEBHOOK_URL")
    response = requests.post(
        webhook_url, 
        json=payload, 
        headers={"Content-Type": "application/json"}
    )

    print(f"TRMNL Response: {response.status_code} - {response.text}")

if __name__ == "__main__":
    main()
