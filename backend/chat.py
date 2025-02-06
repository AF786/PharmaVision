import google.generativeai as genai
from config import Config

# Configure the API key and initialize the model
genai.configure(api_key=Config.API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def get_gemini_response(user_message):
    try:
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        print(f"Error from Gemini API: {e}")
        return "There was an error processing your request."
