import os
from flask import Flask, request, render_template, redirect, flash, session, url_for
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
import tempfile
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from urllib.parse import urlparse

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

# Database connection helper
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    return conn

# Database setup
def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

# Initialize database
init_db()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'error')
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

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

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([name, email, password, confirm_password]):
            flash('All fields are required!', 'error')
            return redirect(url_for('signup'))
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('signup'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'error')
            return redirect(url_for('signup'))
        
        # Check if user already exists
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE email = %s', (email,))
            if c.fetchone():
                conn.close()
                flash('Email already registered!', 'error')
                return redirect(url_for('signup'))
            
            # Hash password and create user
            hashed_password = generate_password_hash(password)
            c.execute('INSERT INTO users (name, email, password) VALUES (%s, %s, %s)',
                      (name, email, hashed_password))
            conn.commit()
            conn.close()
            
            flash('Account created successfully! Please sign in.', 'success')
            return redirect(url_for('signin'))
        except Exception as e:
            print(f"Signup error: {e}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('signup'))
    
    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not all([email, password]):
            flash('All fields are required!', 'error')
            return redirect(url_for('signin'))
        
        # Check credentials
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = c.fetchone()
            conn.close()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_email'] = user['email']
                flash(f'Welcome back, {user["name"]}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid email or password!', 'error')
                return redirect(url_for('signin'))
        except Exception as e:
            print(f"Signin error: {e}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('signin'))
    
    return render_template('signin.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('signin'))

@app.route('/model',methods=['GET','POST'])
@login_required
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

        print("Received request for pill detection")
        try:
            # Initialize Roboflow with API key
            rf = Roboflow(api_key=API_KEY)
            project = rf.workspace().project("pill-recognition-oxvel")
            model = project.version(1).model

            # Validate if the model was successfully loaded
            if model is None:
                return jsonify({"error": "Model failed to load."}), 500
            else:
                print("Model loaded:", model)

            # Check if file is included in the request
            if 'file' not in request.files:
                print("No file part in the request.")
                return jsonify({"error": "No file part in the request."}), 400

            file = request.files['file']

            # Ensure the file has a valid name
            if file.filename == '':
                print("No selected file.")
                return jsonify({"error": "No selected file."}), 400

            # Try to open and process the image
            try:
                image = Image.open(BytesIO(file.read()))
                print("Image opened successfully")  # Check if the image is opened
                # Convert the PIL image to a format that the model can work with
                image_np = np.array(image)  # Convert to a NumPy array
                # Make the prediction
                result = model.predict(image_np, confidence=10, overlap=30).json()
                if 'predictions' in result and result['predictions']:
                    pill_name = result['predictions'][0]['class']
                    return jsonify({
                        "pill_name": pill_name,
                    })
                else:
                    print("No pill detected.")
                    return jsonify({"error": "No pill detected."}), 400

            except Exception as e:
                print("Image processing error:", str(e))
                return jsonify({"error": f"Image processing error: {str(e)}"}), 500

        except Exception as e:
            print("Internal server error:", str(e))
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500
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
@login_required
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

@app.route('/skin',methods=['POST','GET'])
def skin():
    return render_template('skin.html')

@app.route('/detect-skin',methods=['POST'])
def detect_skin_disease():
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

        print("Received request for Disease detection")
        try:
            # Initialize Roboflow with API key
            rf = Roboflow(api_key=API_KEY)
            project = rf.workspace().project("skin-disease-vrvtv")
            model = project.version(1).model

            # Validate if the model was successfully loaded
            if model is None:
                return jsonify({"error": "Model failed to load."}), 500
            else:
                print("Model loaded:", model)

            # Check if file is included in the request
            if 'file' not in request.files:
                print("No file part in the request.")
                return jsonify({"error": "No file part in the request."}), 400

            file = request.files['file']

            # Ensure the file has a valid name
            if file.filename == '':
                print("No selected file.")
                return jsonify({"error": "No selected file."}), 400

            # Try to open and process the image
            try:
                image = Image.open(BytesIO(file.read()))
                print("Image opened successfully")  # Check if the image is opened
                # Convert the PIL image to a format that the model can work with
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp:
                    image_path = temp.name
                    image.save(image_path)
                    print(f"Saved image at temporary path: {image_path}")
                print("Image Saved Successfully!!!")
                result = model.predict(image_path, confidence=20, overlap=30).json()
                print("Prediction result:", result)
                if 'predictions' in result and result['predictions']:
                    disease_name = result['predictions'][0]['class']
                    print("Success - Disease detected:", disease_name)
                    return jsonify({
                        "disease_name": disease_name,
                    })
                else:
                    print("No Disease detected.")
                    return jsonify({"error": "No Disease detected."}), 400

            except Exception as e:
                print("Image processing error:", str(e))
                return jsonify({"error": f"Image processing error: {str(e)}"}), 500

        except Exception as e:
            print("Internal server error:", str(e))
            return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    except Exception as e:
        print(f"Server error: {str(e)}")
        return jsonify({
            "error": "Internal server error. Please try again later."
        }), 500

            
        
if __name__ == "__main__":
    # Run the Flask app
    # app.run("127.0.0.1", port=8080, debug=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
