import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

print("Available models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)

try:
    model = genai.GenerativeModel('gemini-3.5-flash')
    response = model.generate_content('Hello')
    print('Response:', response.text)
except Exception as e:
    print('Error:', e)
