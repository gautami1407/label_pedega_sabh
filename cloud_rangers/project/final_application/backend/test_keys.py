import os
from dotenv import load_dotenv
load_dotenv('.env')

gemini_key = os.getenv('GEMINI_API_KEY', '')
usda_key = os.getenv('USDA_API_KEY', '')
print(f'GEMINI_API_KEY loaded: {bool(gemini_key)}, starts: {gemini_key[:12]}')
print(f'USDA_API_KEY loaded: {bool(usda_key)}, starts: {usda_key[:12]}')

# Test Gemini
try:
    import google.generativeai as genai
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    resp = model.generate_content('Say OK in 2 words')
    print(f'Gemini API: OK -> {resp.text[:60]}')
except Exception as e:
    print(f'Gemini API ERROR: {str(e)[:300]}')

# Test USDA
try:
    import requests
    r = requests.get(
        'https://api.nal.usda.gov/fdc/v1/foods/search',
        params={'api_key': usda_key, 'query': 'apple', 'pageSize': 1},
        timeout=8
    )
    if r.status_code == 200:
        foods = r.json().get('foods', [])
        print(f'USDA API: OK -> found {len(foods)} result(s)')
    else:
        print(f'USDA API ERROR: HTTP {r.status_code} -> {r.text[:200]}')
except Exception as e:
    print(f'USDA API Exception: {str(e)[:200]}')
