import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from a .env file

class Config:
    API_KEY = os.getenv("GEMINI_API_KEY")
