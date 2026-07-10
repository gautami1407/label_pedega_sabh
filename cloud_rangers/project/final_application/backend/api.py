from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from analyzer import Analyzer
from news_service import NewsService
from csv_loader import RegulatoryCSVDatabase
from lps.shared.language import MEDICAL_DISCLAIMER
import os
import base64
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "LPS_CORS_ORIGINS",
        "http://localhost:5000,http://127.0.0.1:5000",
    ).split(",")
    if o.strip()
]

app = Flask(__name__, static_folder='../frontend')
CORS(app, origins=_CORS_ORIGINS)

analyzer = Analyzer()
news_service = NewsService()
csv_db = RegulatoryCSVDatabase()

# ── Static file serving ──────────────────────────────
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

# ═══════════════════════════════════════════════════════
# Product by barcode (GET or POST)
# ═══════════════════════════════════════════════════════
@app.route('/api/product/<barcode>', methods=['POST', 'GET'])
def get_product(barcode):
    """
    Barcode → OpenFoodFacts → CSV Regulatory Check → AI Analysis
    Accepts optional JSON body { preferences: {...userHealthProfile} }
    """
    try:
        preferences = {}
        if request.method == 'POST' and request.is_json:
            data = request.json or {}
            preferences = data.get('preferences', {})

        logger.info(f"Analyzing barcode: {barcode} with prefs: {list(preferences.keys())}")
        result = analyzer.analyze_barcode(barcode, preferences)

        if "error" in result:
            return jsonify(result), 404
        result.setdefault("disclaimer", MEDICAL_DISCLAIMER)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in get_product: {e}")
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════
# Product search by name
# ═══════════════════════════════════════════════════════
@app.route('/api/product/search', methods=['GET'])
def search_product():
    """Search Open Food Facts by product name."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    try:
        results = analyzer.fetcher.search_by_name(query, page_size=5)
        return jsonify({"products": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Error in search_product: {e}")
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════
# Image / OCR Analysis
# ═══════════════════════════════════════════════════════
@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Image → Gemini AI → Six-Factor Analysis
    Accepts JSON body { image: 'data:image/jpeg;base64,...', preferences: {...} }
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.json or {}
    image_data = data.get('image') or data.get('image_data', '')
    preferences = data.get('preferences', {})

    if not image_data:
        return jsonify({"error": "No image data provided. Send 'image' as a base64 data URI."}), 400

    try:
        if ',' in image_data:
            _, encoded = image_data.split(",", 1)
        else:
            encoded = image_data

        image_bytes = base64.b64decode(encoded)

        logger.info(f"Analyzing image ({len(image_bytes)} bytes)…")
        result = analyzer.analyze_image(image_bytes, preferences)
        if isinstance(result, dict) and "error" not in result:
            result.setdefault("disclaimer", MEDICAL_DISCLAIMER)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in analyze: {e}")
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════
# Additive lookup from CSV database
# ═══════════════════════════════════════════════════════
@app.route('/api/additives/<identifier>', methods=['GET'])
def lookup_additive(identifier):
    """Look up a specific additive by E-number or name from the CSV database."""
    try:
        records = csv_db.lookup_additive(identifier)
        if not records:
            return jsonify({"error": f"Additive '{identifier}' not found in database"}), 404

        return jsonify({
            "additive": records[0]['name'],
            "e_number": records[0]['e_number'],
            "records": records
        })
    except Exception as e:
        logger.error(f"Error in lookup_additive: {e}")
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════
# News & Recalls
# ═══════════════════════════════════════════════════════
@app.route('/api/news', methods=['GET'])
def get_news():
    product_name = request.args.get('product')
    news = news_service.fetch_news(product_name if product_name else None)
    return jsonify(news)

# ═══════════════════════════════════════════════════════
# AI Chat Assistant
# ═══════════════════════════════════════════════════════
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    AI Chat — accepts { message: '...', context: {...productContext} }
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.json or {}
    query = data.get('message') or data.get('query', '')
    context = data.get('context')

    if not query:
        return jsonify({"error": "No message provided"}), 400

    logger.info(f"Chat query: {query[:80]}…")
    response_text = analyzer.chat_with_assistant(query, context)
    return jsonify({
        "response": response_text,
        "disclaimer": MEDICAL_DISCLAIMER,
    })

# ═══════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════
@app.route('/api/health', methods=['GET'])
def health():
    payload = {
        "status": "ok",
        "service": "lps-flask-api",
        "csv_loaded": len(csv_db.all_records) > 0,
        "csv_records": len(csv_db.all_records),
        "csv_e_numbers": len(csv_db.by_e_number),
        "quarantined_excluded": csv_db.quarantined_count,
        "disclaimer": MEDICAL_DISCLAIMER,
    }
    if _DEBUG:
        payload["debug"] = {
            "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
            "usda_configured": bool(os.getenv("USDA_API_KEY")),
        }
    return jsonify(payload)

if __name__ == '__main__':
    host = os.getenv("LPS_HOST", "0.0.0.0")
    port = int(os.getenv("LPS_PORT", "5000"))
    app.run(debug=_DEBUG, port=port, host=host)
