# ============================================================
# Label Padegha Sabh — FastAPI Backend v2
# Merged: Auth/Database (HEAD) + Product Intelligence (incoming)
# ============================================================

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import sys
import base64
import json
import re
import logging

# ── sys.path setup ──────────────────────────────────────────
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Optional: Database / Auth ────────────────────────────────
try:
    from database import (
        register_user, login_user, get_user_by_id,
        get_health_profile, update_health_profile,
        save_scan, get_scan_history, get_all_allergens
    )
    DB_AVAILABLE = True
    print("✓ Database module loaded")
except ImportError as e:
    print(f"! Database module not available: {e}")
    DB_AVAILABLE = False

# ── Product Intelligence utils ───────────────────────────────
try:
    from utils.product_lookup import lookup_product
    from utils.data_processor import normalize_product_data, parse_ingredients
    from utils.risk_engine import load_banned_ingredients, check_banned_ingredients, calculate_health_score
    from utils.gemini_integration import GeminiHandler
    from news_service import get_safety_news
    from utils.analysis_engine import analyze_product as run_product_analysis

    try:
        gemini = GeminiHandler()
    except Exception as e:
        print(f"Warning: Gemini not initialized: {e}")
        gemini = None

    BANNED_DB_PATH = os.path.join(_backend_dir, "data", "banned_ingredients.csv")
    banned_df = load_banned_ingredients(BANNED_DB_PATH) if os.path.exists(BANNED_DB_PATH) else None

    UTILS_AVAILABLE = True
    print("✓ Product analysis utils loaded")
except ImportError as e:
    print(f"! Product analysis utils not available: {e}")
    gemini = None
    banned_df = None
    lookup_product = None
    UTILS_AVAILABLE = False

# ── FastAPI app ──────────────────────────────────────────────
app = FastAPI(title="Label Padegha Sabh API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic Models ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class HealthProfileUpdate(BaseModel):
    allergies: Optional[List[str]] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    age: Optional[int] = None
    dietary_preference: Optional[str] = None
    other_allergy: Optional[str] = None
    other_diet: Optional[str] = None
    sensitivities: Optional[str] = None

class AnalysisRequest(BaseModel):
    product_name: Optional[str] = None
    ingredients: Optional[List[str]] = None
    risks: Optional[List[dict]] = None
    image: Optional[str] = None
    preferences: Optional[dict] = None

class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None

class AnalyzeProductRequest(BaseModel):
    barcode: str
    age: Optional[int] = None
    allergies: Optional[List[str]] = None
    conditions: Optional[List[str]] = None
    diet: Optional[str] = None

class ProductRequest(BaseModel):
    query: Optional[str] = None

# ── Auth helper ──────────────────────────────────────────────

def get_current_user(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    user = get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ═══════════════════════════════════════════════════════════
# CORE ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "db_available": DB_AVAILABLE,
        "utils_available": UTILS_AVAILABLE
    }

# ── Auth Routes ──────────────────────────────────────────────

@app.post("/api/auth/register")
async def api_register(request: RegisterRequest):
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    if not request.full_name or not request.email or not request.password:
        raise HTTPException(status_code=400, detail="Missing required fields")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = register_user(request.full_name, request.email, request.password)
    if not user:
        raise HTTPException(status_code=409, detail="Email already registered")
    return {"success": True, "user": user}

@app.post("/api/auth/login")
async def api_login(request: LoginRequest):
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    if not request.email or not request.password:
        raise HTTPException(status_code=400, detail="Missing email or password")
    user = login_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"success": True, "user": user}

@app.get("/api/auth/me")
async def api_me(current_user: dict = Depends(get_current_user)):
    return {"success": True, "user": current_user}

# ── Health Profile Routes ────────────────────────────────────

@app.get("/api/profile")
async def api_get_profile(current_user: dict = Depends(get_current_user)):
    profile = get_health_profile(current_user["id"])
    return {"success": True, "profile": profile or {}}

@app.put("/api/profile")
async def api_update_profile(data: HealthProfileUpdate, current_user: dict = Depends(get_current_user)):
    profile_data = data.dict(exclude_none=True)
    if not update_health_profile(current_user["id"], profile_data):
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return {"success": True, "profile": get_health_profile(current_user["id"])}

# ── Scan History Routes ──────────────────────────────────────

@app.post("/api/scan/save")
async def api_save_scan(scan_data: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    scan_id = save_scan(current_user["id"], scan_data)
    return {"success": True, "scan_id": scan_id}

@app.get("/api/scan/history")
async def api_scan_history(limit: int = 20, current_user: dict = Depends(get_current_user)):
    scans = get_scan_history(current_user["id"], limit)
    return {"success": True, "scans": scans}

@app.get("/api/allergens")
async def api_allergens():
    allergens = get_all_allergens() if DB_AVAILABLE else []
    return {"success": True, "allergens": allergens}

# ═══════════════════════════════════════════════════════════
# PRODUCT INTELLIGENCE ROUTES
# ═══════════════════════════════════════════════════════════

@app.post("/api/analyze-product")
def analyze_product_endpoint(request: AnalyzeProductRequest):
    """
    Unified Product Intelligence Pipeline.
    Input:  barcode + optional user profile
    Output: complete analysis (concern score, ingredients, allergens,
            regulatory, warnings, news, AI summary)

    NOTE (Bug #7 fix): Returns HTTP 200 even when a product is not found,
    with {"error": "..."} in the body. The frontend JS checks `data.error`
    — this only works on a 200 response. A 404/HTTPException was previously
    silently swallowing the error message.
    """
    if not UTILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Product analysis utils not available")

    logger.info(f"=== /api/analyze-product barcode={request.barcode} ===")

    user_profile = {
        "age":        request.age,
        "allergies":  request.allergies  or [],
        "conditions": request.conditions or [],
        "diet":       request.diet       or ""
    }

    result = run_product_analysis(request.barcode, user_profile)

    if result.get("error"):
        logger.warning(f"Product not found: {result['error']}")
        # Return 200 + error field so the frontend data.error check works
        return {"error": result["error"]}

    logger.info(f"Analysis complete. Score={result.get('concern_score', {}).get('score', 'N/A')}")
    return result


@app.get("/api/news")
def news_endpoint(product_name: str, max_articles: int = 10):
    if not UTILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="News service not available")
    try:
        return get_safety_news(product_name, max_articles)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    from config import get_api_key
    api_key = get_api_key("gemini")
    is_placeholder = not api_key or "your_gemini_api_key_here" in api_key

    if not gemini or is_placeholder:
        return {"response": f"AI Chat Mock: '{request.message}' received. (Configure GEMINI_API_KEY to enable)"}
    try:
        if request.context:
            gemini.start_chat(request.context)
        return {"response": gemini.send_message(request.message)}
    except Exception as e:
        return {"response": f"AI error: {str(e)}"}

@app.api_route("/api/product/{barcode}", methods=["GET", "POST"])
def get_product(barcode: str):
    """Fetch product by barcode with risk enrichment."""
    if not UTILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Product utils not available")

    raw_data = lookup_product(barcode)
    if not raw_data:
        raise HTTPException(status_code=404, detail="Product not found")

    product = normalize_product_data(raw_data)
    ingredients_list = parse_ingredients(product.get('ingredients_text', ''))
    risks = check_banned_ingredients(ingredients_list, banned_df) if banned_df is not None else []
    product['parsed_ingredients'] = ingredients_list
    product['risks'] = risks
    product['health_score'] = calculate_health_score(product.get('nutriments', {}))
    return product

@app.post("/api/analyze")
def analyze_legacy(request: AnalysisRequest):
    """Legacy OCR / image analysis endpoint."""
    if not UTILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Analysis utils not available")

    from config import get_api_key
    api_key = get_api_key("gemini")
    is_placeholder = not api_key or "your_gemini_api_key_here" in api_key

    mock_payload = {
        "name": "Coca-Cola (OCR Demo)", "brand": "The Coca-Cola Company",
        "ingredients_text": "carbonated water, sugar, colour (caramel e150d), phosphoric acid, natural flavourings including caffeine",
        "image_url": "",
        "nutriments": {"energy_100g": 180, "sugars_100g": 10.6, "saturated-fat_100g": 0.0,
                       "salt_100g": 0.0, "proteins_100g": 0.0, "fiber_100g": 0.0},
        "categories": "beverages", "nova_group": 4, "nutriscore_grade": "e", "source": "Gemini OCR Mock"
    }

    def _enrich(payload):
        p = normalize_product_data(payload)
        ings = parse_ingredients(p['ingredients_text'])
        risks = check_banned_ingredients(ings, banned_df) if banned_df is not None else []
        p['parsed_ingredients'] = ings
        p['risks'] = risks
        p['health_score'] = calculate_health_score(p.get('nutriments', {}))
        return p

    if request.image:
        if not gemini or is_placeholder:
            return _enrich(mock_payload)
        try:
            header, b64 = request.image.split(",", 1) if "," in request.image else ("", request.image)
            image_bytes = base64.b64decode(b64)
            mime = "image/jpeg"
            if "image/png" in header: mime = "image/png"
            elif "image/webp" in header: mime = "image/webp"
            ocr_text = gemini.analyze_label_image(image_bytes, mime)
            cleaned = re.sub(r"^```(?:json)?\n", "", ocr_text.strip())
            cleaned = re.sub(r"\n```$", "", cleaned).strip()
            return _enrich(json.loads(cleaned))
        except Exception as e:
            print(f"OCR failed ({e}), returning mock")
            return _enrich(mock_payload)

    if not gemini or is_placeholder:
        return {"explanation": "AI Service Unavailable. Configure GEMINI_API_KEY."}
    try:
        explanation = gemini.explain_risks(
            request.product_name or "Unknown",
            request.ingredients or [],
            request.risks or []
        )
        return {"explanation": explanation}
    except Exception as e:
        return {"explanation": f"AI error: {str(e)}"}

# ═══════════════════════════════════════════════════════════
# STATIC FILE SERVING
# ═══════════════════════════════════════════════════════════

frontend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
assets_path = os.path.join(frontend_path, "assets")

if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def read_index():
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Label Padegha Sabh API", "status": "running", "version": "2.0.0"}

@app.get("/{filename}.html")
def read_html(filename: str):
    file_path = os.path.join(frontend_path, f"{filename}.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/{filename}.js")
def read_js(filename: str):
    file_path = os.path.join(frontend_path, f"{filename}.js")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/{filename}.css")
def read_css(filename: str):
    file_path = os.path.join(frontend_path, f"{filename}.css")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 50)
    print("  Label Padegha Sabh API Server")
    print("  Visit: http://127.0.0.1:8000")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
