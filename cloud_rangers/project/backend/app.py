from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sys
import os
import json

# Add current directory to path so we can import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    register_user, login_user, get_user_by_id,
    get_health_profile, update_health_profile,
    save_scan, get_scan_history, get_all_allergens
)

app = FastAPI(title="Label Padegha Sabh API", version="2.0.0")

# Allow all CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try to import optional utils (product lookup, risk engine, Gemini)
# These may fail due to missing dependencies or API keys
try:
    from utils.product_lookup import lookup_product
    from utils.data_processor import normalize_product_data, parse_ingredients
    from utils.risk_engine import load_banned_ingredients, check_banned_ingredients, calculate_health_score
    from utils.gemini_integration import GeminiHandler

    # Initialize Gemini
    try:
        gemini = GeminiHandler()
    except Exception as e:
        print(f"Warning: Gemini not initialized: {e}")
        gemini = None

    # Load Banned Ingredients
    BANNED_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "banned_ingredients.csv")
    if os.path.exists(BANNED_DB_PATH):
        banned_df = load_banned_ingredients(BANNED_DB_PATH)
    else:
        print(f"Warning: Banned ingredients file not found at {BANNED_DB_PATH}")
        banned_df = None

    UTILS_AVAILABLE = True
    print("✓ Product analysis utils loaded successfully")
except ImportError as e:
    print(f"! Product analysis utils not available: {e}")
    print("  (Auth and database features still work)")
    lookup_product = None
    gemini = None
    banned_df = None
    UTILS_AVAILABLE = False


# ── Pydantic Models ──

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


# ── Helper: Get user from header ──

def get_current_user(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Simple auth using user ID header."""
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    user = get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

# ── Auth Routes ──

@app.post("/api/auth/register")
async def api_register(request: RegisterRequest):
    """Register a new user."""
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
    """Login a user."""
    if not request.email or not request.password:
        raise HTTPException(status_code=400, detail="Missing email or password")
    
    user = login_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    return {"success": True, "user": user}


@app.get("/api/auth/me")
async def api_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return {"success": True, "user": current_user}


# ── Health Profile Routes ──

@app.get("/api/profile")
async def api_get_profile(current_user: dict = Depends(get_current_user)):
    """Get health profile for current user."""
    profile = get_health_profile(current_user["id"])
    if not profile:
        return {"success": True, "profile": {}}
    return {"success": True, "profile": profile}


@app.put("/api/profile")
async def api_update_profile(data: HealthProfileUpdate, current_user: dict = Depends(get_current_user)):
    """Update health profile for current user."""
    profile_data = data.dict(exclude_none=True)
    if not update_health_profile(current_user["id"], profile_data):
        raise HTTPException(status_code=500, detail="Failed to update profile")
    
    profile = get_health_profile(current_user["id"])
    return {"success": True, "profile": profile}


# ── Scan History Routes ──

@app.post("/api/scan/save")
async def api_save_scan(scan_data: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """Save a product scan to history."""
    scan_id = save_scan(current_user["id"], scan_data)
    return {"success": True, "scan_id": scan_id}


@app.get("/api/scan/history")
async def api_scan_history(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Get scan history for current user."""
    scans = get_scan_history(current_user["id"], limit)
    return {"success": True, "scans": scans}


# ── Allergen Reference Route ──

@app.get("/api/allergens")
async def api_allergens():
    """Get list of known allergens from the reference database."""
    allergens = get_all_allergens()
    return {"success": True, "allergens": allergens}


# ── Product Routes (if utils available) ──

if UTILS_AVAILABLE:
    class AnalysisRequest(BaseModel):
        product_name: str
        ingredients: List[str]
        risks: List[dict]

    @app.api_route("/api/product/{barcode}", methods=["GET", "POST"])
    async def get_product(barcode: str):
        """Fetch product by barcode and enrich with risk data."""
        raw_data = lookup_product(barcode)
        if not raw_data:
            raise HTTPException(status_code=404, detail="Product not found")
        
        product = normalize_product_data(raw_data)
        ingredients_list = parse_ingredients(product.get('ingredients_text', ''))
        
        risks = []
        if banned_df is not None:
            risks = check_banned_ingredients(ingredients_list, banned_df)
        
        product['parsed_ingredients'] = ingredients_list
        product['risks'] = risks
        product['health_score'] = calculate_health_score(product.get('nutriments', {}))
        
        return product

    @app.post("/api/analyze")
    async def analyze_product(request: AnalysisRequest):
        """Analyze product ingredients with AI."""
        if not gemini:
            raise HTTPException(status_code=503, detail="AI Service Unavailable")
        explanation = gemini.explain_risks(request.product_name, request.ingredients, request.risks)
        return {"explanation": explanation}

    print("✓ Product API routes registered")
else:
    print("! Product API routes not available (missing utils)")


# ── Static File Serving ──

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
    return {"message": "Label Padegha Sabh API", "status": "running"}

@app.get("/{filename}.html")
async def read_html(filename: str):
    file_path = os.path.join(frontend_path, f"{filename}.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/{filename}.js")
async def read_js(filename: str):
    file_path = os.path.join(frontend_path, f"{filename}.js")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/{filename}.css")
async def read_css(filename: str):
    file_path = os.path.join(frontend_path, f"{filename}.css")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("  Label Padegha Sabh API Server")
    print("  Visit: http://127.0.0.1:5000")
    print("="*50 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=5000)