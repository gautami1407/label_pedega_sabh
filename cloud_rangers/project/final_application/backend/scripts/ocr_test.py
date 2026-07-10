// scripts/ocr_test.py
import base64, json, time, sys, pathlib, requests

if len(sys.argv) != 2:
    print('Usage: python ocr_test.py <image_path>')
    sys.exit(1)

image_path = pathlib.Path(sys.argv[1])
if not image_path.is_file():
    print(f'Image not found: {image_path}')
    sys.exit(1)

with open(image_path, 'rb') as f:
    img_b64 = base64.b64encode(f.read()).decode('utf-8')

payload = json.dumps({"image_data": img_b64})
url = 'http://localhost:8000/api/v1/scan/ocr'
headers = {'Content-Type': 'application/json'}

start = time.time()
resp = requests.post(url, headers=headers, data=payload)
elapsed = time.time() - start

print('---RESULT---')
print(json.dumps({
    'status_code': resp.status_code,
    'elapsed_seconds': elapsed,
    'response': resp.json() if resp.headers.get('Content-Type','').startswith('application/json') else resp.text
}, indent=2))
