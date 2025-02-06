import os
from flask import Flask, request, render_template, redirect, flash
from flask import jsonify
from pathlib import Path
from backend.detection import get_gemini_response, analyze_pill_image
from dotenv import load_dotenv
import pandas as pd
import google.generativeai as genai
from roboflow import Roboflow
from PIL import Image
from io import BytesIO
import numpy as np
from flask_mail import Mail, Message
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()
API_KEY = os.environ.get('ROBOFLOW_API_KEY')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

app = Flask(__name__, template_folder='frontend', static_folder='frontend/static')
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
 
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg','webp' }
app.config['MAX_CONTENT_LENGTH']= 16*1024*1024

# Add these configurations after creating the Flask app
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('SENDER_EMAIL')
app.config['MAIL_PASSWORD'] = os.environ.get('SENDER_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('SENDER_EMAIL')

mail = Mail(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Create vision prompt
vision_prompt = """
You are a medical image analyzer. Examine this image of a medication/pill and provide:

1. Visual Description:
Color and shape
Numbers or letters visible
Size and distinctive features
Any markings or imprints

2. Identification (if possible):
Medication name if clearly identifiable
Drug class or category
Strength/dosage if visible

Be very specific about what you can see. If you cannot identify the medication with certainty, focus on describing the physical characteristics you observe.
"""

@app.route('/', methods= ['GET']) 
def index():
    return render_template('index.html')


@app.route('/about', methods=['GET', 'POST'])
def about():
    return render_template('about.html')


@app.route('/product', methods=['GET','POST'])
def product():
    return render_template('product.html')

@app.route('/contact', methods=['GET','POST'])
def contact():
    return render_template('contactus.html')

@app.route('/model',methods=['GET','POST'])
def model():
    return render_template('model.html')


@app.route('/submit_form', methods=['POST'])
def submit_form():
    try:
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        # Create email content
        recipient = os.environ.get('RECIPIENT_EMAIL')
        subject = f"New Contact Form Submission from {name}"
        body = f"""
        New contact form submission:
        
        Name: {name}
        Email: {email}
        Message: {message}
        """

        # Create and send email
        msg = MIMEMultipart()
        msg['From'] = os.environ.get('SENDER_EMAIL')
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Create SMTP session
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.environ.get('SENDER_EMAIL'), os.environ.get('SENDER_PASSWORD'))
        
        # Send email
        server.send_message(msg)
        server.quit()

        # Store in Excel
        form_data = {
            'Name': [name],
            'Email': [email],
            'Message': [message]
        }
        write_data = pd.DataFrame(form_data)
        try:
            with pd.ExcelWriter('contact_responses.xlsx', mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                write_data.to_excel(writer, index=False, header=False, startrow=writer.sheets['Sheet1'].max_row)
        except FileNotFoundError:
            write_data.to_excel('contact_responses.xlsx', index=False)

        # Flash success message before redirect
        flash('Your email has been successfully sent!', 'success')
        return redirect('/contact')

    except Exception as e:
        print(f"Error: {str(e)}")
        flash('An error occurred while sending your message.', 'error')
        return redirect('/contact')

@app.route('/pill-detect', methods=['POST'])
def pill_detect():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # List of allowed image extensions
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
        if not file.filename.lower().endswith(tuple(ALLOWED_EXTENSIONS)):
            return jsonify({"error": "Invalid file type. Please upload an image (PNG, JPG, JPEG, WEBP)"}), 400

        try:
            # Process the image
            image = Image.open(BytesIO(file.read()))
            
            # Image preprocessing
            # Resize image for consistent processing
            image = image.resize((800, 800))
            # Convert to RGB if image is in RGBA
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            
            # Convert to numpy array
            image_np = np.array(image)

            # Make prediction
            result = model.predict(
                image_np,
                confidence=60,
                overlap=30
            ).json()

            if 'predictions' in result and result['predictions']:
                # Get the top prediction
                prediction = result['predictions'][0]
                pill_name = prediction['class']
                confidence = prediction['confidence']

                # Get detailed information about the detected pill
                system_prompt = (
                    "Provide detailed information about this medication:\n"
                    f"The detected pill appears to be {pill_name} (Confidence: {confidence:.1f}%)\n"
                    "Include:\n"
                    "1. Primary uses and benefits\n"
                    "2. Common dosage information\n"
                    "3. Important safety warnings\n"
                    "4. Common side effects\n"
                    "5. Drug interactions to avoid"
                )
                
                pill_info = get_gemini_response(f"Tell me about {pill_name} medication", system_prompt)

                return jsonify({
                    "pill_name": pill_name,
                    "confidence": f"{confidence:.1f}%",
                    "information": pill_info
                })
            else:
                return jsonify({
                    "error": "No pill detected in the image. Please ensure the image is clear and well-lit."
                }), 400

        except Exception as e:
            print(f"Image processing error: {str(e)}")
            return jsonify({
                "error": "Error processing image. Please ensure the image is clear and try again."
            }), 500

    except Exception as e:
        print(f"Server error: {str(e)}")
        return jsonify({
            "error": "Internal server error. Please try again later."
        }), 500

@app.route('/get-drug-info', methods=['GET','POST'])
def get_drug_info_route():
    data = request.form
    pill_name = data.get('drug_name')
    system_prompt = (
        "Format the response in clear sections, with each point on a new line and in bold:\n\n"
        "1. Uses\n"
        "[List each use on a new line  with bullet points]\n\n"
        "2. Dosage Information\n"
        "[List each dosage detail on a new line with bullet points]\n\n"
        "3. Side Effects\n"
        "[List each side effect on a new line with bullet points]\n\n"
        "4. Safety Information\n"
        "[List each safety point on a new line with bullet points]\n\n"
        "Rules:\n"
        "- Write each point as a complete sentence\n"
        "- Start each line directly with the information\n"
        "- Do not use any symbols, bullets, or asterisks\n"
        "- Keep points sequential and clear"
    )
    user_message = (
        f"Provide Detailed information about {pill_name} in a clear, sequential format. "
        "Each point should be on its own line without any special characters or formatting."
    )
    
    gemini_response = get_gemini_response(user_message, system_prompt)
    formatted_response = gemini_response.replace("\n", "<br>")
    pill_info = {
        "pill_name": pill_name,
        "information": formatted_response
    }
    return render_template('model.html', pill_info=pill_info)

@app.route('/guide')
def how_to_use():
    return render_template('guide.html')

@app.route('/chatbot', methods=['GET'])
def chatbot():
    return render_template('chatbot.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json['message']
        system_prompt = (
            "You are a knowledgeable medical assistant. When asked about medications:\n\n"
            "1. Provide detailed information about the medication's uses, effects, and important details\n"
            "2. Use clear, simple language that's easy to understand\n"
            "3. Include important safety information and common side effects\n"
            "4. Always start with a brief medical disclaimer\n"
            "5. Format the response with proper spacing for readability\n"
            "6. End with a reminder to consult healthcare professionals\n\n"
            "Keep responses informative but conversational, as if explaining to a patient."
        )
        
        response = get_gemini_response(user_message, system_prompt)
        return jsonify({'response': response})
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error. Please try again.'})

if __name__ == "__main__":
    # Run the Flask app
    app.run("127.0.0.1", port=8080, debug=True)
    
