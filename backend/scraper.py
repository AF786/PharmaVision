import requests
from bs4 import BeautifulSoup
import re
import base64
import os
from PIL import Image
from io import BytesIO
import google.generativeai as genai

# Local database of common pill imprints (more reliable than AI)
COMMON_IMPRINTS = {
    '770': {'name': 'Acetaminophen', 'dosage': '500 mg', 'brand': 'Anacin Aspirin Free'},
    'L484': {'name': 'Acetaminophen', 'dosage': '500 mg', 'brand': 'Generic'},
    '44 159': {'name': 'Acetaminophen', 'dosage': '500 mg', 'brand': 'Generic'},
    'TYLENOL': {'name': 'Acetaminophen', 'dosage': 'Various', 'brand': 'Tylenol'},
    'I-2': {'name': 'Ibuprofen', 'dosage': '200 mg', 'brand': 'Generic'},
    'IBU 200': {'name': 'Ibuprofen', 'dosage': '200 mg', 'brand': 'Generic'},
    'ADVIL': {'name': 'Ibuprofen', 'dosage': 'Various', 'brand': 'Advil'},
    'BAYER': {'name': 'Aspirin', 'dosage': '325 mg', 'brand': 'Bayer'},
    'IP 109': {'name': 'Hydrocodone/Acetaminophen', 'dosage': '5mg/325mg', 'brand': 'Generic'},
    'M 30': {'name': 'Oxycodone', 'dosage': '30 mg', 'brand': 'Generic'},
    '93 150': {'name': 'Amphetamine/Dextroamphetamine', 'dosage': '30 mg', 'brand': 'Generic'},
    'A 215': {'name': 'Oxycodone', 'dosage': '30 mg', 'brand': 'Generic'},
    'RP 10': {'name': 'Oxycodone', 'dosage': '10 mg', 'brand': 'Generic'},
}

def google_lens_search(image_bytes):
    """
    Use Gemini Vision API to extract pill imprint, then search local database
    Requires GEMINI_API_KEY in environment (no billing required)
    """
    try:
        gemini_key = os.environ.get('GEMINI_API_KEY')
        
        if not gemini_key:
            print("ERROR: GEMINI_API_KEY not set - add to .env file")
            return None
        
        # Configure Gemini
        genai.configure(api_key=gemini_key)
        
        # Convert bytes to PIL Image
        image = Image.open(BytesIO(image_bytes))
        
        # Convert RGBA to RGB if needed
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        
        print("🔍 Using Gemini Vision API...")
        
        # Use Gemini 2.5 Flash (supports vision natively)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = """
You are a pill imprint extraction specialist. Your ONLY job is to find and extract text/numbers from the pill.

DO NOT try to identify the medication. ONLY extract what you see.

TASK: Find the IMPRINT CODE
Look carefully at the pill surface for:
- Numbers (e.g., "770", "44", "500", "93")
- Letters + Numbers (e.g., "L484", "IP109", "M30", "A215")
- Text (e.g., "TYLENOL", "ADVIL", "BAYER")
- Symbols or logos

Check BOTH sides of the pill if visible.
Report EXACTLY what you see - no interpretation, no guessing.

OUTPUT FORMAT:
Imprint: [exact text/numbers you see, or "NONE" if nothing visible]
Shape: [round/oval/oblong/capsule]
Color: [color]

Example outputs:
Imprint: 770
Shape: Round
Color: White

Imprint: L484
Shape: Oblong
Color: White

Imprint: NONE
Shape: Round
Color: Blue
"""
        
        response = model.generate_content([prompt, image])
        
        if response and response.text:
            result_text = response.text
            print(f"✓ Gemini Vision extracted:\n{result_text}")
            
            # Parse the imprint
            imprint_match = re.search(r'Imprint:\s*([^\n]+)', result_text, re.IGNORECASE)
            shape_match = re.search(r'Shape:\s*([^\n]+)', result_text, re.IGNORECASE)
            color_match = re.search(r'Color:\s*([^\n]+)', result_text, re.IGNORECASE)
            
            imprint = imprint_match.group(1).strip() if imprint_match else None
            shape = shape_match.group(1).strip() if shape_match else "Unknown"
            color = color_match.group(1).strip() if color_match else "Unknown"
            
            print(f"Extracted - Imprint: '{imprint}', Shape: {shape}, Color: {color}")
            
            # Search local database for accurate results
            if imprint and imprint.upper() not in ['NONE', 'UNKNOWN', 'NOT VISIBLE', 'NO VISIBLE IMPRINT']:
                clean_imprint = imprint.strip().upper()
                
                # Check exact match in local database
                if clean_imprint in COMMON_IMPRINTS:
                    pill_data = COMMON_IMPRINTS[clean_imprint]
                    pill_name = f"{pill_data['name']}"
                    if pill_data['brand'] and pill_data['brand'] != 'Generic':
                        pill_name += f" ({pill_data['brand']})"
                    
                    print(f"✓ Found in local database: {pill_name} {pill_data['dosage']}")
                    return {
                        'pill_name': pill_name,
                        'dosage': pill_data['dosage'],
                        'source': f'Imprint: {imprint}'
                    }
                
                # Try partial matches
                for word in imprint.split():
                    if len(word) >= 2:
                        for db_imprint, pill_data in COMMON_IMPRINTS.items():
                            if word.upper() in db_imprint or db_imprint in word.upper():
                                pill_name = f"{pill_data['name']}"
                                if pill_data['brand'] and pill_data['brand'] != 'Generic':
                                    pill_name += f" ({pill_data['brand']})"
                                
                                print(f"✓ Partial match in database: {pill_name} {pill_data['dosage']}")
                                return {
                                    'pill_name': pill_name,
                                    'dosage': pill_data['dosage'],
                                    'source': f'Imprint: {imprint}'
                                }
                
                # If not in database, try online search
                print(f"🔍 Imprint '{imprint}' not in local database, trying online search...")
                drugs_result = search_drugs_com_imprint(imprint)
                if drugs_result:
                    print(f"✓ Found online: {drugs_result['pill_name']}")
                    return drugs_result
                
                # Return what we found even if not identified
                return {
                    'pill_name': f"Unknown - Imprint: {imprint}",
                    'dosage': f"Shape: {shape}, Color: {color}",
                    'source': 'Gemini Vision'
                }
            else:
                print("⚠ No imprint detected on pill")
                return None
        
        return None
        
    except Exception as e:
        print(f"Error with Gemini Vision: {e}")
        import traceback
        traceback.print_exc()
        return None

def search_drugs_com_imprint(imprint):
    """Search drugs.com by text"""
    try:
        if not imprint or len(imprint) < 1:
            return None
        
        imprint = imprint.strip().replace('\n', ' ')
        url = f'https://www.drugs.com/imprints.php?imprint={imprint}'
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            pill_results = soup.find_all('div', class_='ddc-media')
            
            if pill_results:
                link = pill_results[0].find('a')
                if link:
                    pill_name = link.get_text(strip=True)
                    dosage_match = re.search(r'(\d+\s*(?:mg|mcg|g|ml))', pill_name, re.IGNORECASE)
                    dosage = dosage_match.group(1) if dosage_match else 'See product info'
                    
                    return {
                        'pill_name': pill_name,
                        'dosage': dosage,
                        'source': 'Drugs.com'
                    }
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_drug_info(imprint):
    url = f'https://www.drugs.com/imprints.php?{imprint}&color=&shape=0'
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content,'html.parser')
    elem = soup.find()
    print(elem.prettify())
    

if __name__ == '__main__':
    name = input("Enter Drug: ")
    get_drug_info(name)