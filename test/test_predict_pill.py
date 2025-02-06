import google.generativeai as genai
from dotenv import load_dotenv
import os
from roboflow import Roboflow
from testpill_name import get_drug_info
import pprint

load_dotenv()
API_KEY = os.environ.get('ROBOFLOW_API_KEY')
def predict_pill(img_path_or_url):
    rf = Roboflow(api_key=API_KEY)
    project = rf.workspace().project("pill-recognition-oxvel")
    model = project.version(1).model
    if model is None:
        print("Model failed to load.")
    else:
        print("Model loaded successfully.")

    print(f"Model: {model}")
    print(f"Image Path: {img_path_or_url}")
    # infer on an image hosted elsewhere
    if model:
        result = model.predict(image_path=img_path_or_url, confidence=40, overlap=30).json()
        result.update({"info": get_drug_info(result)})
    else:
        print("Model is None, cannot predict.")
    return None

pprint(predict_pill("PharmaVision-master\\uploads\\images.jpg"))