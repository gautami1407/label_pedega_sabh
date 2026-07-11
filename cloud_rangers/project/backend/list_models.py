# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_api_key

key = get_api_key("gemini")
print(f"Key prefix: {key[:15]}...")

print()
print("--- Trying google-genai (new SDK) ---")
try:
    from google import genai
    client = genai.Client(api_key=key)
    # List available models
    models = client.models.list()
    print("Available models:")
    for m in models:
        name = getattr(m, 'name', str(m))
        print(f"  {name}")
except Exception as e:
    print(f"Error listing models: {e}")

print()
print("--- Quick generate test with gemini-1.5-flash ---")
try:
    from google import genai
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Say 'hello world' only."
    )
    print(f"Success: {resp.text.strip()}")
except Exception as e:
    print(f"gemini-1.5-flash failed: {e}")

print()
print("--- Try gemini-2.0-flash ---")
try:
    from google import genai
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Say 'hello world' only."
    )
    print(f"Success: {resp.text.strip()}")
except Exception as e:
    print(f"gemini-2.0-flash failed: {e}")
