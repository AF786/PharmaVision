from roboflow import Roboflow
from dotenv import load_dotenv
import os
import cv2
from pathlib import Path
from typing import Union, List
import google.generativeai as genai
import time
from PIL import Image
import numpy as np
from io import BytesIO

load_dotenv()
API_KEY = os.environ.get('ROBOFLOW_API_KEY')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
print(API_KEY)

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def analyze_pill_image(image_data, prompt):
    """
    Analyze pill image using Gemini Vision
    """
    try:
        # Convert bytes to PIL Image for preprocessing
        image = Image.open(BytesIO(image_data))
        
        # Convert RGBA to RGB if needed
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        
        # Convert back to bytes
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()

        # Initialize Gemini Vision model
        model = genai.GenerativeModel('gemini-pro-vision')
        
        # Create the message with image and prompt
        response = model.generate_content([
            prompt,
            {'mime_type': 'image/jpeg', 'data': img_byte_arr}
        ])
        
        print("Gemini Vision Response:", response.text)  # Debug logging
        return response.text if response else None
        
    except Exception as e:
        print(f"Error analyzing image in analyze_pill_image: {str(e)}")
        return None

def get_gemini_response(user_message, system_prompt):
    try:
        # Add timeout handling
        start_time = time.time()
        timeout = 10  # 10 seconds timeout

        # Simplified prompt to reduce response time
        full_prompt = f"{system_prompt}\n{user_message}"
        
        # Set generation config for faster response
        response = model.generate_content(
            full_prompt,
            generation_config={
                'temperature': 0.7,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 1024,
            }
        )

        # Check for timeout
        if time.time() - start_time > timeout:
            return "Request timed out. Please try again."

        if response.text:
            return response.text
        return "No response generated"

    except Exception as e:
        print(f"Error from Gemini API: {e}")
        if "rate limit" in str(e).lower():
            return "Service is busy. Please try again in a moment."
        return "There was an error processing your request."

def get_drug_info(pill_name):
    system_prompt = (
        "Format the response in clear sections like this:\n\n"
        "1. Uses\n"
        "Provide uses in clear, separate lines\n\n"
        "2. Dosage Information\n"
        "Provide dosage details in clear, separate lines\n\n"
        "3. Side Effects\n"
        "List side effects in clear, separate lines\n\n"
        "4. Safety Information\n"
        "Provide safety information in clear, separate lines\n\n"
        "Rules:\n"
        "- Start each section with the numbered heading\n"
        "- Put each point on a new line\n"
        "- Make information clear and detailed\n"
        "- Do not use any special characters or HTML tags"
    )
    
    user_message = f"Provide detailed information about {pill_name}"
    
    gemini_response = get_gemini_response(user_message, system_prompt)
    formatted_response = gemini_response.replace("\n", "<br>")
    pill_info = {
        "pill_name": pill_name,
        "information": formatted_response
    }
    return pill_info

def image_with_bboxes(frame: Union[Path, cv2.Mat], face_data: List[dict]) -> cv2.Mat:
    if isinstance(frame, Path):
        image = cv2.imread(str(frame))
    elif isinstance(frame, cv2.Mat):
        image = frame.copy()
    else:
        raise TypeError('frame type must be Path or cv2.Mat Object')

    boxes = [face['bbox'].values() for face in face_data]
    for (left, top, right, bottom) in boxes:
        cv2.rectangle(image, (left, top), (right, bottom), (0,255,0), 2)

    return image

def preprocess_image(image):
    """
    Preprocess image for better pill detection
    """
    # Convert to numpy array if needed
    if isinstance(image, Image.Image):
        image = np.array(image)
    
    # Normalize image
    image = image.astype(np.float32) / 255.0
    
    # Apply contrast enhancement
    image = np.clip(image * 1.2, 0, 1)
    
    # Convert back to uint8
    image = (image * 255).astype(np.uint8)
    
    return image

def get_pill_info(image, model):
    """
    Enhanced pill detection and information retrieval
    """
    # Preprocess image
    processed_image = preprocess_image(image)
    
    # Make prediction
    prediction = model.predict(
        processed_image,
        confidence=60,
        overlap=30
    ).json()
    
    return prediction



