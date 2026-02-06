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
You are a pharmaceutical expert specializing in pill identification. Analyze this pill/medication image and identify it.

TASK: Identify the medication by examining:
1. Imprint codes (numbers, letters, or text on the pill surface)
2. Shape (round, oval, oblong, capsule, etc.)
3. Color and appearance
4. Size and distinctive features
5. Brand name if visible

Provide your identification in this exact format:

Medication Name: [Full generic name or brand name]
Dosage: [Strength like 500mg, 10mg, etc., or "Unknown" if not determinable]
Imprint: [Text/numbers visible on pill, or "None visible"]
Description: [Brief description of physical appearance]

If you can identify the medication with reasonable confidence, provide the name.
If you cannot confidently identify it, state "Unknown" for Medication Name but still describe what you see.

Be specific and accurate. Use your knowledge of common medications and their appearances.
"""
        
        response = model.generate_content([prompt, image])
        
        if response and response.text:
            result_text = response.text
            print(f"✓ Gemini Vision identified:\n{result_text}")
            
            # Parse the response
            med_name_match = re.search(r'Medication Name:\s*([^\n]+)', result_text, re.IGNORECASE)
            dosage_match = re.search(r'Dosage:\s*([^\n]+)', result_text, re.IGNORECASE)
            imprint_match = re.search(r'Imprint:\s*([^\n]+)', result_text, re.IGNORECASE)
            desc_match = re.search(r'Description:\s*([^\n]+)', result_text, re.IGNORECASE)
            
            medication_name = med_name_match.group(1).strip() if med_name_match else "Unknown"
            dosage = dosage_match.group(1).strip() if dosage_match else "Unknown"
            imprint = imprint_match.group(1).strip() if imprint_match else "None visible"
            description = desc_match.group(1).strip() if desc_match else ""
            
            print(f"Identified - Medication: '{medication_name}', Dosage: {dosage}, Imprint: {imprint}")
            
            # Check if identification was successful
            if medication_name and medication_name.upper() not in ['UNKNOWN', 'CANNOT IDENTIFY', 'NOT IDENTIFIABLE', 'UNCLEAR']:
                # Successfully identified
                source_info = f"Imprint: {imprint}" if imprint != "None visible" else "Visual identification"
                
                print(f"✓ Successfully identified: {medication_name}")
                return {
                    'pill_name': medication_name,
                    'dosage': dosage,
                    'source': source_info
                }
            else:
                # Could not identify, but try online search if imprint is available
                if imprint and imprint.upper() not in ['NONE', 'UNKNOWN', 'NOT VISIBLE', 'NO VISIBLE IMPRINT', 'NONE VISIBLE']:
                    print(f"🔍 Medication not identified, trying online search with imprint '{imprint}'...")
                    drugs_result = search_drugs_com_imprint(imprint)
                    if drugs_result:
                        print(f"✓ Found online: {drugs_result['pill_name']}")
                        return drugs_result
                
                # Return description if identification failed
                print("⚠ Could not identify medication")
                return {
                    'pill_name': f"Unknown Medication",
                    'dosage': description if description else "Unable to identify",
                    'source': f'Imprint: {imprint}' if imprint != "None visible" else 'No imprint visible'
                }
        
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