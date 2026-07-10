@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls\cloud_rangers\project\backend"
echo === Testing endpoints === > ep_test.txt 2>&1

echo --- GET / (index) --- >> ep_test.txt
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\python.exe -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/'); print('STATUS:', r.status)" >> ep_test.txt 2>&1

echo --- GET /health --- >> ep_test.txt
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\python.exe -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health'); print(r.read().decode())" >> ep_test.txt 2>&1

echo --- GET /scanner.html --- >> ep_test.txt
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\python.exe -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/scanner.html'); print('STATUS:', r.status)" >> ep_test.txt 2>&1

echo --- GET /dashboard.html --- >> ep_test.txt
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\python.exe -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/dashboard.html'); print('STATUS:', r.status)" >> ep_test.txt 2>&1

echo --- POST /api/analyze-product (Maggi barcode) --- >> ep_test.txt
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\python.exe -c "import urllib.request,json; data=json.dumps({'barcode':'8901030895489'}).encode(); req=urllib.request.Request('http://127.0.0.1:8000/api/analyze-product',data=data,headers={'Content-Type':'application/json'},method='POST'); r=urllib.request.urlopen(req); resp=json.loads(r.read()); print('score=',resp.get('concern_score',{}).get('score'), 'product=',resp.get('product',{}).get('name'))" >> ep_test.txt 2>&1

type ep_test.txt
