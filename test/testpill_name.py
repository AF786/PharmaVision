import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(api_key="GEMINI_API_KEY")
model = genai.GenerativeModel("gemini-1.5-flash")

def get_gemini_response(user_message):
    try:
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        print(f"Error from Gemini API: {e}")
        return "There was an error processing your request."

def get_drug_info(pill_name):
    user_message = (
        f"Provide detailed information about the pill '{pill_name}', including:"
        " - Side effects\n"
        " - Dosage instructions\n"
        " - Chemical composition\n"
        " - Safety information\n"
    )
    gemini_response = get_gemini_response(user_message)
    pill_info = {
        "pill_name": pill_name,
        "information": gemini_response
    }
    return pill_info

print(get_drug_info("Amoxicilin"))