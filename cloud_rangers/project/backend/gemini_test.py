# -*- coding: utf-8 -*-
import sys, os, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 1. Check key is loaded correctly
from config import get_api_key
key = get_api_key("gemini")
print(f"Gemini key loaded: {'YES - ' + key[:12] + '...' if key and 'your_gemini' not in key else 'NO - still placeholder'}")

# 2. Test Gemini directly
print()
print("--- Testing Gemini API directly (google-genai SDK) ---")
try:
<<<<<<< Updated upstream
    from google import genai
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Say hello in one sentence.",
    )
    print(f"Gemini response: {response.text.strip()}")
=======
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    resp = model.generate_content("Say hello in one sentence.")
    print(f"Gemini response: {resp.text.strip()}")
>>>>>>> Stashed changes
except Exception as e:
    print(f"Gemini error: {e}")

# 3. Test full pipeline barcode -> AI summary
print()
print("--- Testing barcode 8901058851311 via HTTP ---")
try:
    payload = json.dumps({"barcode": "8901058851311"}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/analyze-product",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=25)
    body = json.loads(resp.read())

    p  = body.get("product", {})
    cs = body.get("concern_score", {})
    print(f"Product  : {p.get('name')} by {p.get('brand')}")
    print(f"Source   : {p.get('source')}")
    print(f"Score    : {cs.get('score')}/100 - {cs.get('level')}")
    print(f"Factors  : {cs.get('factors', [])[:6]}")
    print(f"Allergens: {[a['allergen'] for a in body.get('allergens', [])]}")
    print(f"Ingredients ({len(body.get('ingredients',[]))}): {body.get('ingredients',[])[:5]}")
    print(f"Regulatory: {len(body.get('regulatory',[]))} concerns")
    print(f"News     : {len(body.get('news', []))} articles")
    print(f"Nova     : {body.get('nova', {}).get('name')}")
    print(f"AI Summary: {body.get('ai_summary', '')[:200]}")
    print()
    print("FULL JSON (truncated):")
    print(json.dumps({k: v for k, v in body.items() if k not in ('ingredient_explanations',)}, indent=2, default=str)[:2000])
except Exception as e:
    print(f"HTTP test error: {e}")
