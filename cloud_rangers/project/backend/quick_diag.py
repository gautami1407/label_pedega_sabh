# -*- coding: utf-8 -*-
import sys, os, json, urllib.request, urllib.error, traceback
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BARCODE = "8901058851311"
API = "http://127.0.0.1:8000"

print(f"=== Diagnosing barcode: {BARCODE} ===")
print()

# Step 1: hit the HTTP endpoint
print("--- HTTP POST /api/analyze-product ---")
try:
    payload = json.dumps({"barcode": BARCODE}).encode()
    req = urllib.request.Request(
        f"{API}/api/analyze-product",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=20)
    body = json.loads(resp.read())
    print("HTTP 200 OK")
    print(json.dumps(body, indent=2, default=str)[:3000])
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()

print()
# Step 2: check what product-eval-engine.js thinks API_BASE is
js_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "js", "product-eval-engine.js"))
print(f"--- product-eval-engine.js API_BASE ---")
with open(js_path, encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 'API_BASE' in line or 'api/analyze' in line.lower():
            print(f"  line {i}: {line.rstrip()}")

print()
# Step 3: check product-result.html for loading container state
html_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "product-result.html"))
print(f"--- product-result.html loading container ---")
with open(html_path, encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 'loadingContainer' in line or 'productContainer' in line or 'errorContainer' in line:
            print(f"  line {i}: {line.rstrip()}")
