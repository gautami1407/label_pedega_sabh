"""
AI Food Safety Intelligence System
Production-grade Streamlit application for real-time food product analysis.
Architecture: Service Layer Pattern (ProductService, AdditiveService, BanService, ScoringEngine, AIService, UI)

Input methods:
  1. Live camera barcode scanner (streamlit-webrtc + OpenCV / pyzbar)
  2. Manual barcode text entry
Both methods route through the same _process_barcode() pipeline → identical results.
"""

import os
import json
import time
import hashlib
import threading
import re

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
from google import genai

# ── Optional barcode/camera deps (gracefully degrade if missing) ──────────────
try:
    import cv2
    import numpy as np
    import av
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration, VideoProcessorBase
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False

# ─────────────────────────────────────────────
# BOOTSTRAP
# ─────────────────────────────────────────────
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
USDA_API_KEY   = os.environ.get("USDA_API_KEY", "")
CACHE_DIR      = os.path.join(os.path.expanduser("~"), ".food_intel_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# CSV paths — place your files here or update the paths
ADDITIVES_CSV_PATH  = os.environ.get("ADDITIVES_CSV", "additives_database.csv")
BANNED_PRODUCTS_CSV = os.environ.get("BANNED_CSV",    "banned_products.csv")

RTC_CONFIGURATION = (
    RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
    if WEBRTC_AVAILABLE else None
)

st.set_page_config(
    page_title="Food Safety Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBAL STYLES
# ─────────────────────────────────────────────
def _inject_styles() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

    /* ── Page chrome ── */
    .stApp { background: #0d1117; color: #e6edf3; }
    section[data-testid="stSidebar"] { background: #161b22; border-right: 1px solid #30363d; }

    /* ── App header ── */
    .app-header { padding: 1.5rem 0 1rem; border-bottom: 1px solid #21262d; margin-bottom: 1.5rem; }
    .app-header h1 { font-size: 1.6rem; font-weight: 600; color: #e6edf3; letter-spacing: -0.02em; margin: 0; }
    .app-header p  { font-size: 0.82rem; color: #8b949e; margin: 0.25rem 0 0; }

    /* ── Cards ── */
    .card {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
    }

    /* ── Score badge ── */
    .score-badge {
        display: inline-flex; align-items: center; gap: 0.4rem;
        padding: 0.2rem 0.65rem;
        border-radius: 4px;
        font-family: 'DM Mono', monospace;
        font-size: 0.78rem; font-weight: 500;
    }
    .badge-low      { background: #0d2f1d; color: #3fb950; border: 1px solid #238636; }
    .badge-moderate { background: #2b2000; color: #d29922; border: 1px solid #9e6a03; }
    .badge-high     { background: #2b1400; color: #f0883e; border: 1px solid #bd561d; }
    .badge-critical { background: #2b0e12; color: #f85149; border: 1px solid #da3633; }

    /* ── Additive pills ── */
    .pill-high     { background:#2b0e12; color:#f85149; border:1px solid #da3633; border-radius:4px; padding:0.2rem 0.5rem; font-size:0.75rem; display:inline-block; margin:0.15rem; }
    .pill-moderate { background:#2b1400; color:#f0883e; border:1px solid #bd561d; border-radius:4px; padding:0.2rem 0.5rem; font-size:0.75rem; display:inline-block; margin:0.15rem; }
    .pill-low      { background:#0d2f1d; color:#3fb950; border:1px solid #238636; border-radius:4px; padding:0.2rem 0.5rem; font-size:0.75rem; display:inline-block; margin:0.15rem; }
    .pill-unknown  { background:#1c2128; color:#8b949e; border:1px solid #30363d;  border-radius:4px; padding:0.2rem 0.5rem; font-size:0.75rem; display:inline-block; margin:0.15rem; }

    /* ── Warning / info banners ── */
    .warn-banner {
        background:#2b0e12; border:1px solid #da3633; border-radius:6px;
        padding: 0.75rem 1rem; margin: 0.5rem 0; font-size: 0.85rem; color: #f85149;
    }
    .info-banner {
        background:#0d1c2f; border:1px solid #1f6feb; border-radius:6px;
        padding: 0.75rem 1rem; margin: 0.5rem 0; font-size: 0.85rem; color: #58a6ff;
    }
    .success-banner {
        background:#0d2f1d; border:1px solid #238636; border-radius:6px;
        padding: 0.75rem 1rem; margin: 0.5rem 0; font-size: 0.85rem; color: #3fb950;
    }

    /* ── Scanner box ── */
    .scanner-box {
        background: #161b22;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px dashed #1f6feb;
        text-align: center;
        margin: 1rem 0;
    }

    /* ── Section heading ── */
    .section-title { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #8b949e; margin-bottom: 0.75rem; }

    /* ── Metric row ── */
    .metric-row { display:flex; gap:1rem; flex-wrap:wrap; margin-bottom:1rem; }
    .metric-box { background:#1c2128; border:1px solid #30363d; border-radius:6px; padding:0.65rem 1rem; min-width:110px; }
    .metric-box .m-label { font-size:0.7rem; color:#8b949e; }
    .metric-box .m-value { font-size:1.05rem; font-weight:600; color:#e6edf3; font-family:'DM Mono',monospace; }
    .metric-box .m-unit  { font-size:0.68rem; color:#6e7681; }

    /* ── Grade chips ── */
    .grade-chip {
        display:inline-flex; align-items:center; justify-content:center;
        width:32px; height:32px; border-radius:50%;
        font-weight:700; font-size:0.9rem; color:#fff;
    }

    /* ── AI report ── */
    .ai-report { font-size:0.87rem; line-height:1.75; color:#c9d1d9; }
    .ai-report h3 { font-size:0.82rem; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; color:#58a6ff; margin:1rem 0 0.25rem; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] { gap:0; border-bottom:1px solid #21262d; }
    .stTabs [data-baseweb="tab"] { padding:0.6rem 1rem; font-size:0.82rem; color:#8b949e; background:transparent; border:none; border-bottom:2px solid transparent; }
    .stTabs [aria-selected="true"] { color:#e6edf3; border-bottom-color:#1f6feb; }

    /* ── Input ── */
    .stTextInput > div > div > input {
        background:#1c2128; border:1px solid #30363d; color:#e6edf3;
        border-radius:6px; font-size:0.9rem;
    }
    .stTextInput > div > div > input:focus { border-color:#1f6feb; }

    /* ── Buttons ── */
    .stButton > button {
        background:#238636; border:1px solid #2ea043; color:#fff;
        border-radius:6px; font-size:0.85rem; padding:0.45rem 1.2rem;
        font-weight:500;
    }
    .stButton > button:hover { background:#2ea043; }

    /* scrollbar */
    ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background:#161b22; }
    ::-webkit-scrollbar-thumb { background:#30363d; border-radius:3px; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# BARCODE SCANNER (Camera)  ← ported from code 2
# ─────────────────────────────────────────────
if WEBRTC_AVAILABLE:
    class BarcodeScanner(VideoProcessorBase):
        """
        WebRTC video processor that detects barcodes frame-by-frame using
        OpenCV's built-in BarcodeDetector (opencv-contrib-python) with a
        fallback to pyzbar when the contrib module is not installed.
        """

        def __init__(self):
            self.lock = threading.Lock()
            self.detected_barcode: str | None = None
            self._use_pyzbar = False

            # Try OpenCV contrib barcode detector first
            try:
                self._detector = cv2.barcode.BarcodeDetector()
            except AttributeError:
                try:
                    self._detector = cv2.barcode_BarcodeDetector()  # older naming
                except AttributeError:
                    self._detector = None
                    # Fall back to pyzbar
                    try:
                        from pyzbar import pyzbar as _pyzbar  # noqa: F401
                        self._use_pyzbar = True
                    except ImportError:
                        pass  # no barcode support at all

        def recv(self, frame: "av.VideoFrame") -> "av.VideoFrame":  # type: ignore[name-defined]
            img = frame.to_ndarray(format="bgr24")

            try:
                if self._detector is not None:
                    retval, decoded_info, decoded_type, points = self._detector.detectAndDecode(img)
                    if retval and decoded_info:
                        with self.lock:
                            self.detected_barcode = decoded_info[0]
                        if points is not None and len(points) > 0:
                            pts = points.astype(int)
                            for i in range(len(pts[0])):
                                p1 = tuple(pts[0][i])
                                p2 = tuple(pts[0][(i + 1) % len(pts[0])])
                                cv2.line(img, p1, p2, (0, 255, 0), 3)
                            cv2.putText(img, decoded_info[0], (20, 50),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)

                elif self._use_pyzbar:
                    from pyzbar import pyzbar
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    barcodes = pyzbar.decode(gray)
                    if barcodes:
                        code = barcodes[0].data.decode("utf-8")
                        with self.lock:
                            self.detected_barcode = code
                        cv2.putText(img, code, (20, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
            except Exception:
                pass  # never crash the video stream

            return av.VideoFrame.from_ndarray(img, format="bgr24")


# ─────────────────────────────────────────────
# SERVICE 1 — PRODUCT SERVICE
# ─────────────────────────────────────────────
class ProductService:
    OFF_BASE  = "https://world.openfoodfacts.org/api/v0"
    USDA_BASE = "https://api.nal.usda.gov/fdc/v1"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "FoodSafetyIntel/2.0"

    # ── cache helpers ──────────────────────────
    def _cache_path(self, key: str) -> str:
        h = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{h}.json")

    def _from_cache(self, key: str, ttl: int = 86400):
        p = self._cache_path(key)
        if os.path.exists(p):
            try:
                with open(p) as f:
                    obj = json.load(f)
                if time.time() - obj.get("ts", 0) < ttl:
                    return obj["data"]
            except Exception:
                pass
        return None

    def _to_cache(self, key: str, data) -> None:
        try:
            with open(self._cache_path(key), "w") as f:
                json.dump({"data": data, "ts": time.time()}, f)
        except Exception:
            pass

    # ── OpenFoodFacts ──────────────────────────
    def fetch_from_openfoodfacts(self, barcode: str) -> dict | None:
        cached = self._from_cache(f"off:{barcode}")
        if cached:
            return cached
        try:
            r = self._session.get(
                f"{self.OFF_BASE}/product/{barcode}.json", timeout=10
            )
            r.raise_for_status()
            raw = r.json()
            if raw.get("status") != 1:
                return None
            p = raw["product"]
            result = {
                "barcode":    barcode,
                "name":       p.get("product_name") or p.get("product_name_en") or "Unknown Product",
                "brand":      p.get("brands", ""),
                "category":   (
                    p.get("categories_tags", [""])[0].replace("en:", "").replace("-", " ").title()
                    if p.get("categories_tags")
                    else p.get("categories", "")
                ),
                "countries":  p.get("countries", ""),
                "image":      p.get("image_front_url") or p.get("image_url"),
                "ingredients_text": p.get("ingredients_text", ""),
                "nutrients":  p.get("nutriments", {}),
                "nutri_score": (p.get("nutrition_grades") or "").upper(),
                "nova_group":  p.get("nova_group"),
                "ecoscore":   (p.get("ecoscore_grade") or "").upper(),
                "allergens":  [
                    a.replace("en:", "").replace("-", " ").title()
                    for a in p.get("allergens_tags", [])
                ],
                "additives":  [
                    a.replace("en:", "").upper()
                    for a in p.get("additives_tags", [])
                ],
                "labels":     p.get("labels", ""),
            }
            self._to_cache(f"off:{barcode}", result)
            return result
        except Exception:
            return None

    # ── USDA FoodData Central ──────────────────
    def fetch_from_usda(self, product_name: str) -> dict:
        if not USDA_API_KEY or not product_name:
            return {}
        cached = self._from_cache(f"usda:{product_name}")
        if cached:
            return cached
        try:
            r = self._session.get(
                f"{self.USDA_BASE}/foods/search",
                params={"api_key": USDA_API_KEY, "query": product_name, "pageSize": 1},
                timeout=10,
            )
            data = r.json()
            if not data.get("foods"):
                return {}
            food      = data["foods"][0]
            nutrients = {}
            MAP = {
                "Energy":               ("energy-kcal_100g", 1),
                "Protein":              ("proteins_100g",    1),
                "Carbohydrate":         ("carbohydrates_100g", 1),
                "Total lipid (fat)":    ("fat_100g",         1),
                "Sugars, total":        ("sugars_100g",      1),
                "Fiber, total dietary": ("fiber_100g",       1),
                "Sodium":               ("salt_100g",        0.0025),  # mg → g salt approx
            }
            for n in food.get("foodNutrients", []):
                name = n.get("nutrientName", "")
                for k, (field, factor) in MAP.items():
                    if k in name:
                        nutrients[field] = (n.get("value") or 0) * factor
                        break
            self._to_cache(f"usda:{product_name}", nutrients)
            return nutrients
        except Exception:
            return {}

    # ── Unified fetch ──────────────────────────
    def fetch_product(self, barcode: str) -> dict | None:
        product = self.fetch_from_openfoodfacts(barcode)
        if not product:
            return None
        # Supplement nutrients from USDA if sparse
        if len(product.get("nutrients", {})) < 4:
            usda = self.fetch_from_usda(product["name"])
            product["nutrients"].update(usda)
        return product


# ─────────────────────────────────────────────
# SERVICE 2 — ADDITIVE SERVICE
# ─────────────────────────────────────────────
class AdditiveService:
    def __init__(self):
        self._db = self._load()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def _load_csv(path: str) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(path)
            df.columns = df.columns.str.strip()
            return df
        except Exception:
            return None

    def _load(self) -> pd.DataFrame | None:
        if os.path.exists(ADDITIVES_CSV_PATH):
            return self._load_csv(ADDITIVES_CSV_PATH)
        # Inline fallback sample
        return pd.DataFrame({
            "E_number":        ["E102","E110","E129","E951","E621","E320","E250","E211","E160b"],
            "Additive_name":   ["Tartrazine","Sunset Yellow","Allura Red","Aspartame","MSG","BHA","Sodium Nitrite","Sodium Benzoate","Annatto"],
            "Risk_Level":      ["High","High","High","Medium","Medium","High","High","Medium","Low"],
            "Banned_Countries":["Norway,Austria","Norway,Finland","","","","Japan","EU(restricted)","",""],
            "Health_Concern":  [
                "Hyperactivity, Allergies","Hyperactivity, Allergies","Hyperactivity",
                "Headaches, PKU risk","Headaches","Carcinogen potential",
                "Cancer concern (processed meats)","DNA damage at high dose","Hives in sensitive individuals"
            ],
        })

    def analyze_additives(self, additive_codes: list[str]) -> list[dict]:
        results = []
        if not additive_codes or self._db is None:
            return results
        db    = self._db.copy()
        e_col = next((c for c in db.columns if "e_number" in c.lower() or c.lower() == "e_number"), None)
        name_col = (
            next((c for c in db.columns if "name" in c.lower() and "additive" in c.lower()), None)
            or next((c for c in db.columns if "name" in c.lower()), None)
        )
        risk_col = next((c for c in db.columns if "risk" in c.lower()), None)
        ban_col  = next((c for c in db.columns if "ban" in c.lower() or "country" in c.lower()), None)
        con_col  = next((c for c in db.columns if "concern" in c.lower() or "health" in c.lower() or "effect" in c.lower()), None)

        for code in additive_codes:
            code  = code.strip().upper()
            match = db[db[e_col].str.upper() == code] if e_col else pd.DataFrame()
            if not match.empty:
                row = match.iloc[0]
                results.append({
                    "code":             code,
                    "name":             str(row[name_col]) if name_col else "Unknown",
                    "risk_level":       str(row[risk_col]).strip() if risk_col else "Unknown",
                    "banned_countries": str(row[ban_col]).split(",") if ban_col and pd.notna(row[ban_col]) else [],
                    "health_concern":   str(row[con_col]) if con_col and pd.notna(row[con_col]) else "",
                })
            else:
                results.append({"code": code, "name": "Unknown", "risk_level": "Unknown",
                                 "banned_countries": [], "health_concern": ""})
        return results


# ─────────────────────────────────────────────
# SERVICE 3 — PRODUCT BAN SERVICE
# ─────────────────────────────────────────────
class ProductBanService:
    def __init__(self):
        self._db = self._load()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def _load_csv(path: str) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(path)
            df.columns = df.columns.str.strip()
            return df
        except Exception:
            return None

    def _load(self) -> pd.DataFrame | None:
        if os.path.exists(BANNED_PRODUCTS_CSV):
            return self._load_csv(BANNED_PRODUCTS_CSV)
        return None

    def check_product_ban(self, product_name: str, barcode: str = "") -> list[dict]:
        if self._db is None or not product_name:
            return []
        name_lower  = product_name.lower()
        name_col    = next((c for c in self._db.columns if "product" in c.lower() or "name" in c.lower()), None)
        country_col = next((c for c in self._db.columns if "country" in c.lower() or "ban" in c.lower()), None)
        reason_col  = next((c for c in self._db.columns if "reason" in c.lower() or "note" in c.lower()), None)
        barcode_col = next((c for c in self._db.columns if "barcode" in c.lower() or "code" in c.lower()), None)
        if not name_col:
            return []
        mask = self._db[name_col].str.lower().str.contains(name_lower, na=False)
        if barcode and barcode_col:
            mask = mask | (self._db[barcode_col].astype(str) == str(barcode))
        hits    = self._db[mask]
        results = []
        for _, row in hits.iterrows():
            results.append({
                "country": str(row[country_col]) if country_col else "Unknown",
                "reason":  str(row[reason_col])  if reason_col  else "See local regulations",
            })
        return results


# ─────────────────────────────────────────────
# SERVICE 4 — SCORING ENGINE
# ─────────────────────────────────────────────
class ScoringEngine:
    THRESHOLDS = {
        "sugar_warning":   10.0,
        "sugar_critical":  20.0,
        "salt_warning":    1.0,
        "salt_critical":   2.5,
        "sat_fat_warning": 5.0,
        "sat_fat_critical":10.0,
        "fat_warning":     17.5,
    }

    def calculate_concern_score(
        self,
        nutrients: dict,
        additive_results: list[dict],
        ban_hits: list[dict],
    ) -> int:
        score = 0
        n       = nutrients
        sugar   = n.get("sugars_100g",            0) or 0
        salt    = n.get("salt_100g",               0) or 0
        sat_fat = n.get("saturated-fat_100g",      0) or 0
        fat     = n.get("fat_100g",                0) or 0
        fiber   = n.get("fiber_100g",              0) or 0

        if sugar >= self.THRESHOLDS["sugar_critical"]:
            score += 25
        elif sugar >= self.THRESHOLDS["sugar_warning"]:
            score += 10 + int((sugar - self.THRESHOLDS["sugar_warning"]) /
                               (self.THRESHOLDS["sugar_critical"] - self.THRESHOLDS["sugar_warning"]) * 15)

        if salt >= self.THRESHOLDS["salt_critical"]:
            score += 20
        elif salt >= self.THRESHOLDS["salt_warning"]:
            score += 8 + int((salt - self.THRESHOLDS["salt_warning"]) /
                              (self.THRESHOLDS["salt_critical"] - self.THRESHOLDS["salt_warning"]) * 12)

        if sat_fat >= self.THRESHOLDS["sat_fat_critical"]:
            score += 15
        elif sat_fat >= self.THRESHOLDS["sat_fat_warning"]:
            score += int((sat_fat / self.THRESHOLDS["sat_fat_critical"]) * 15)

        if fat >= self.THRESHOLDS["fat_warning"]:
            score += 10

        score -= min(8, int(fiber * 0.8))

        for a in additive_results:
            rl = (a.get("risk_level") or "").lower()
            if rl == "high":
                score += 8
            elif rl == "medium":
                score += 3
            elif rl == "low":
                score += 1

        if ban_hits:
            score += min(20, len(ban_hits) * 10)

        return max(0, min(100, score))

    def determine_risk_label(self, score: int) -> tuple[str, str, str]:
        """Returns (label, css_class, hex_color)."""
        if score <= 20:
            return "Low Risk",      "badge-low",      "#3fb950"
        elif score <= 50:
            return "Moderate Risk", "badge-moderate", "#d29922"
        elif score <= 80:
            return "High Concern",  "badge-high",     "#f0883e"
        else:
            return "Critical",      "badge-critical", "#f85149"

    def personalized_warnings(
        self,
        nutrients: dict,
        additive_results: list[dict],
        user_type: str,
    ) -> list[str]:
        warnings    = []
        n           = nutrients
        sugar       = n.get("sugars_100g",           0) or 0
        salt        = n.get("salt_100g",              0) or 0
        sat_fat     = n.get("saturated-fat_100g",     0) or 0
        fat         = n.get("fat_100g",               0) or 0
        high_add    = [a for a in additive_results if (a.get("risk_level") or "").lower() == "high"]

        if user_type == "Diabetic":
            if sugar > 5:
                warnings.append(f"High sugar content ({sugar:.1f}g/100g) — exceeds diabetic tolerance. Avoid.")
            if n.get("carbohydrates_100g", 0) > 30:
                warnings.append("High carbohydrate load — monitor blood glucose carefully.")
        if user_type == "Child":
            if high_add:
                names = ", ".join(a["name"] for a in high_add[:3] if a["name"] != "Unknown")
                warnings.append(f"High-risk additives detected ({names or 'see additives tab'}) — may affect neurobehaviour in children.")
            if sugar > 8:
                warnings.append("Excessive sugar for children — linked to dental issues and metabolic effects.")
        if user_type == "Pregnant":
            if high_add:
                warnings.append("High-risk additives present — consult your physician before consuming.")
            if salt > 1.5:
                warnings.append("Elevated sodium — may contribute to hypertension risk during pregnancy.")
        if user_type == "Heart Patient":
            if sat_fat > 5:
                warnings.append(f"Saturated fat ({sat_fat:.1f}g/100g) exceeds heart-patient threshold of 5g.")
            if salt > 1.0:
                warnings.append(f"High sodium/salt ({salt:.2f}g/100g) — increases cardiovascular risk.")
            if fat > 17.5:
                warnings.append("Total fat content is high — limit portion size.")
        if user_type == "General Adult":
            if sugar > 20:
                warnings.append("Very high sugar — exceeds WHO daily guidelines with moderate serving.")
            if salt > 2.5:
                warnings.append("Very high salt — well above daily recommended intake.")
        return warnings


# ─────────────────────────────────────────────
# SERVICE 5 — AI SERVICE
# ─────────────────────────────────────────────
class AIService:
    MODEL = "gemini-2.0-flash"

    def __init__(self):
        if GEMINI_API_KEY:
            try:
                self._client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception:
                self._client = None
        else:
            self._client = None

    def _structured_prompt(
        self,
        product_name: str,
        ingredients: str,
        nutrients: dict,
        additive_analysis: list[dict],
        ban_status: list[dict],
        user_type: str,
    ) -> str:
        nutrient_str = "\n".join(f"  {k}: {v}" for k, v in nutrients.items() if v)
        additive_str = "\n".join(
            f"  {a['code']} ({a['name']}): Risk={a['risk_level']}, Concern={a['health_concern']}"
            for a in additive_analysis
        ) or "  None detected"
        ban_str = (
            "\n".join(f"  Banned in {b['country']} — {b['reason']}" for b in ban_status)
            if ban_status else "  Not flagged in loaded database"
        )
        return f"""You are a certified food safety and regulatory expert.

Analyze this product strictly using the provided data only. Do not hallucinate.

PRODUCT: {product_name}

INGREDIENTS:
{ingredients or "Not available"}

NUTRIENTS (per 100g):
{nutrient_str or "  Not available"}

ADDITIVES ANALYSIS:
{additive_str}

BAN STATUS:
{ban_str}

USER TYPE: {user_type}

Respond ONLY in these labeled sections (no extra commentary):

1. Overall Risk Level
State exactly one of: Safe / Moderate / High / Critical

2. Key Risk Drivers
List the top 3 specific reasons for the risk level. If data is missing, state "Insufficient data."

3. Additive Safety Summary
Summarize the safety concern of detected additives in 2–3 sentences.

4. Suitability for {user_type}
Is this product suitable? State clearly and explain in 2 sentences.

5. Long-Term Health Implications
2–3 sentences on regular consumption risks.

6. Final Recommendation
One direct sentence. No hedging.
"""

    @st.cache_data(show_spinner=False, ttl=3600)
    def generate_health_report(
        _self,
        product_name: str,
        ingredients: str,
        nutrients_json: str,
        additive_json: str,
        ban_json: str,
        user_type: str,
    ) -> str:
        if _self._client is None:
            return "_AI analysis unavailable — check GEMINI_API_KEY._"
        nutrients = json.loads(nutrients_json)
        additives = json.loads(additive_json)
        bans      = json.loads(ban_json)
        prompt    = _self._structured_prompt(
            product_name, ingredients, nutrients, additives, bans, user_type
        )
        try:
            resp = _self._client.models.generate_content(model=_self.MODEL, contents=prompt)
            return resp.text if resp and resp.text else "_No response from AI._"
        except Exception as e:
            return f"_AI error: {e}_"

    def format_report_html(self, raw_text: str) -> str:
        sections = {
            "1. Overall Risk Level":          "Overall Risk Level",
            "2. Key Risk Drivers":            "Key Risk Drivers",
            "3. Additive Safety Summary":     "Additive Safety Summary",
            "4. Suitability":                 "Suitability",
            "5. Long-Term Health Implications":"Long-Term Health Implications",
            "6. Final Recommendation":        "Final Recommendation",
        }
        html  = '<div class="ai-report">'
        lines = raw_text.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            matched  = False
            for key, label in sections.items():
                if stripped.startswith(key) or (
                    stripped[:3].strip().rstrip(".").isdigit()
                    and label.lower() in stripped.lower()
                ):
                    html += f"<h3>{label}</h3>"
                    rest = re.sub(r"^\d+\.\s*[^:]+:", "", stripped).strip()
                    if rest:
                        html += f"<p>{rest}</p>"
                    matched = True
                    break
            if not matched and stripped:
                html += f"<p>{stripped}</p>"
        html += "</div>"
        return html


# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────
def _grade_color(grade: str) -> str:
    return {
        "A": "#238636", "B": "#85bb2f", "C": "#9e6a03", "D": "#bd561d", "E": "#da3633"
    }.get(grade.upper(), "#30363d")


def _render_grade_chip(label: str, value: str) -> str:
    if not value or value.strip() in ("-", ""):
        return f'<span style="color:#6e7681;font-size:0.75rem">{label}: —</span>'
    color = _grade_color(value)
    return (
        f'<span style="font-size:0.72rem;color:#8b949e">{label}</span>&nbsp;'
        f'<span class="grade-chip" style="background:{color}">{value}</span>'
    )


def _concern_gauge(score: int, color: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode   = "gauge+number",
        value  = score,
        domain = {"x": [0, 1], "y": [0, 1]},
        number = {"font": {"size": 32, "color": color, "family": "DM Mono"}},
        gauge  = {
            "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "#30363d",
                     "tickfont": {"color": "#6e7681", "size": 10}},
            "bar":  {"color": color, "thickness": 0.25},
            "bgcolor": "#1c2128",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  20], "color": "#0d2f1d"},
                {"range": [20, 50], "color": "#2b2000"},
                {"range": [50, 80], "color": "#2b1400"},
                {"range": [80,100], "color": "#2b0e12"},
            ],
        },
    ))
    fig.update_layout(
        height=200, margin={"t": 10, "b": 10, "l": 20, "r": 20},
        paper_bgcolor="#161b22", plot_bgcolor="#161b22",
        font={"color": "#e6edf3"},
    )
    return fig


# ─────────────────────────────────────────────
# CORE PIPELINE  (single source of truth)
# ─────────────────────────────────────────────
def _process_barcode(
    barcode: str,
    product_svc:  ProductService,
    additive_svc: AdditiveService,
    ban_svc:      ProductBanService,
    scorer:       ScoringEngine,
) -> dict | None:
    """
    Fetch and enrich a product by barcode.
    Called identically from camera scan AND manual search — guarantees same result.
    Returns enriched dict or None.
    """
    product = product_svc.fetch_product(barcode)
    if not product:
        return None
    additives = additive_svc.analyze_additives(product.get("additives", []))
    bans      = ban_svc.check_product_ban(product.get("name", ""), barcode)
    score     = scorer.calculate_concern_score(product.get("nutrients", {}), additives, bans)
    product["_additives_analyzed"] = additives
    product["_ban_hits"]           = bans
    product["_concern_score"]      = score
    return product


# ─────────────────────────────────────────────
# PRODUCT DISPLAY  (shared by both input paths)
# ─────────────────────────────────────────────
def _render_product(product: dict, scorer: ScoringEngine, ai_svc: AIService, user_type: str):
    nutrients = product.get("nutrients", {})
    additives = product.get("_additives_analyzed", [])
    bans      = product.get("_ban_hits", [])
    score     = product.get("_concern_score", 0)
    label, badge_cls, badge_color = scorer.determine_risk_label(score)
    warnings  = scorer.personalized_warnings(nutrients, additives, user_type)

    st.markdown("---")

    # ── Product header ────────────────────────
    c1, c2 = st.columns([1, 3], gap="large")
    with c1:
        if product.get("image"):
            st.image(product["image"], width=160)
        else:
            st.markdown(
                '<div style="width:160px;height:160px;background:#1c2128;border:1px solid #30363d;'
                'border-radius:8px;display:flex;align-items:center;justify-content:center;'
                'font-size:2rem">📦</div>',
                unsafe_allow_html=True,
            )
    with c2:
        st.markdown(f"### {product.get('name','Unknown Product')}")
        st.markdown(
            f'<p style="color:#8b949e;font-size:0.85rem;margin-top:-0.5rem">'
            f"{product.get('brand','') or 'Unknown brand'} &nbsp;·&nbsp; "
            f"{product.get('category','') or 'Uncategorized'} &nbsp;·&nbsp; "
            f"Barcode: <code style='font-size:0.8rem'>{product.get('barcode','')}</code></p>",
            unsafe_allow_html=True,
        )
        nutri = product.get("nutri_score", "")
        nova  = str(product.get("nova_group", "") or "")
        eco   = product.get("ecoscore", "")
        st.markdown(
            '<div style="display:flex;gap:1.5rem;align-items:center;margin:0.5rem 0">'
            + _render_grade_chip("Nutri-Score", nutri)
            + _render_grade_chip("NOVA", nova)
            + _render_grade_chip("Eco-Score", eco)
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<span class="score-badge {badge_cls}" style="font-size:0.9rem;padding:0.3rem 0.9rem">'
            f"Concern Score {score}/100 — {label}</span>",
            unsafe_allow_html=True,
        )

    # ── Alerts ────────────────────────────────
    for w in warnings:
        st.markdown(f'<div class="warn-banner">⚠ {w}</div>', unsafe_allow_html=True)

    if bans:
        ban_countries = ", ".join(set(b["country"] for b in bans))
        st.markdown(
            f'<div class="warn-banner">🚫 <strong>Product flagged</strong> — restrictions found in: {ban_countries}</div>',
            unsafe_allow_html=True,
        )

    allergens = product.get("allergens", [])
    if allergens:
        st.markdown(
            f'<div class="warn-banner">⚑ <strong>Allergens:</strong> {", ".join(allergens)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────
    t_overview, t_ingredients, t_nutrition, t_additives, t_bans, t_ai = st.tabs([
        "Overview", "Ingredients", "Nutrition", "Additives", "Ban Info", "AI Report"
    ])

    # Overview
    with t_overview:
        col_gauge, col_info = st.columns([1, 2], gap="large")
        with col_gauge:
            st.plotly_chart(_concern_gauge(score, badge_color), use_container_width=True, config={"displayModeBar": False})
            st.markdown(
                f'<p style="text-align:center;color:#8b949e;font-size:0.78rem">Concern Score for <strong>{user_type}</strong></p>',
                unsafe_allow_html=True,
            )
        with col_info:
            st.markdown('<p class="section-title">Nutritional Snapshot (per 100g)</p>', unsafe_allow_html=True)
            snap = [
                ("Sugar",    nutrients.get("sugars_100g",        0), "g"),
                ("Salt",     nutrients.get("salt_100g",          0), "g"),
                ("Fat",      nutrients.get("fat_100g",           0), "g"),
                ("Sat. Fat", nutrients.get("saturated-fat_100g", 0), "g"),
                ("Protein",  nutrients.get("proteins_100g",      0), "g"),
                ("Fiber",    nutrients.get("fiber_100g",         0), "g"),
                ("Energy",   nutrients.get("energy-kcal_100g",   0), "kcal"),
            ]
            metric_html = '<div class="metric-row">'
            for m_label, m_val, m_unit in snap:
                metric_html += (
                    f'<div class="metric-box">'
                    f'<div class="m-label">{m_label}</div>'
                    f'<div class="m-value">{float(m_val or 0):.1f}</div>'
                    f'<div class="m-unit">{m_unit}/100g</div>'
                    f'</div>'
                )
            metric_html += "</div>"
            st.markdown(metric_html, unsafe_allow_html=True)

            high_risk = [a for a in additives if (a.get("risk_level") or "").lower() == "high"]
            st.markdown('<p class="section-title" style="margin-top:1rem">Risk Factors</p>', unsafe_allow_html=True)
            rf_html = '<div class="metric-row">'
            rf_html += f'<div class="metric-box"><div class="m-label">High-Risk Additives</div><div class="m-value" style="color:#f85149">{len(high_risk)}</div></div>'
            rf_html += f'<div class="metric-box"><div class="m-label">Total Additives</div><div class="m-value">{len(additives)}</div></div>'
            rf_html += f'<div class="metric-box"><div class="m-label">Ban Flags</div><div class="m-value" style="color:{"#f85149" if bans else "#3fb950"}">{len(bans)}</div></div>'
            rf_html += "</div>"
            st.markdown(rf_html, unsafe_allow_html=True)

    # Ingredients
    with t_ingredients:
        st.markdown('<p class="section-title">Full Ingredient List</p>', unsafe_allow_html=True)
        ing = product.get("ingredients_text", "")
        if ing:
            st.markdown(
                f'<div class="card" style="font-size:0.87rem;line-height:1.8;color:#c9d1d9">{ing}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="info-banner">Ingredient data not available from OpenFoodFacts.</div>', unsafe_allow_html=True)

    # Nutrition
    with t_nutrition:
        st.markdown('<p class="section-title">Detailed Nutritional Values (per 100g)</p>', unsafe_allow_html=True)
        nutrient_map = {
            "energy-kcal_100g":   ("Energy",          "kcal"),
            "proteins_100g":      ("Protein",          "g"),
            "carbohydrates_100g": ("Carbohydrates",    "g"),
            "sugars_100g":        ("of which Sugars",  "g"),
            "fat_100g":           ("Fat",              "g"),
            "saturated-fat_100g": ("Saturated Fat",    "g"),
            "fiber_100g":         ("Dietary Fibre",    "g"),
            "salt_100g":          ("Salt",             "g"),
            "sodium_100g":        ("Sodium",           "g"),
        }
        rows = []
        for k, (name, unit) in nutrient_map.items():
            v = nutrients.get(k)
            if v is not None:
                rows.append({"Nutrient": name, "Per 100g": f"{float(v):.2f} {unit}"})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.markdown('<div class="info-banner">No nutritional data available.</div>', unsafe_allow_html=True)

    # Additives
    with t_additives:
        st.markdown('<p class="section-title">Additive Risk Analysis</p>', unsafe_allow_html=True)
        if not additives:
            st.markdown('<div class="info-banner">No additives detected in this product.</div>', unsafe_allow_html=True)
        else:
            pills_html = ""
            for a in additives:
                rl  = (a.get("risk_level") or "unknown").lower()
                cls = {"high": "pill-high", "medium": "pill-moderate", "low": "pill-low"}.get(rl, "pill-unknown")
                pills_html += f'<span class="{cls}">{a["code"]}</span>'
            st.markdown(pills_html, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            for a in additives:
                rl    = a.get("risk_level") or "Unknown"
                color = {"High": "#f85149", "Medium": "#d29922", "Low": "#3fb950"}.get(rl, "#8b949e")
                ban_text = ", ".join([b.strip() for b in a.get("banned_countries", []) if b.strip()]) or "None"
                st.markdown(
                    f'<div class="card" style="border-left:3px solid {color};padding-left:1rem">'
                    f'<strong style="color:{color}">{a["code"]}</strong> &nbsp;·&nbsp; {a["name"]}<br>'
                    f'<span style="font-size:0.8rem;color:#8b949e">Risk: <strong style="color:{color}">{rl}</strong>'
                    f' &nbsp;|&nbsp; Banned in: {ban_text}</span><br>'
                    f'<span style="font-size:0.82rem;color:#c9d1d9">{a.get("health_concern","")}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Ban info
    with t_bans:
        st.markdown('<p class="section-title">Product Ban Status</p>', unsafe_allow_html=True)
        if bans:
            for b in bans:
                st.markdown(
                    f'<div class="warn-banner">'
                    f'<strong>🚫 {b["country"]}</strong><br>'
                    f'<span style="font-size:0.83rem">{b["reason"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="info-banner">No ban records found in loaded database for this product.</div>',
                unsafe_allow_html=True,
            )
            if not os.path.exists(BANNED_PRODUCTS_CSV):
                st.caption(f"Note: Banned products CSV not found at `{BANNED_PRODUCTS_CSV}`. Set BANNED_CSV env var.")

    # AI Report
    with t_ai:
        st.markdown('<p class="section-title">Gemini AI Health Assessment</p>', unsafe_allow_html=True)
        if not GEMINI_API_KEY:
            st.markdown(
                '<div class="warn-banner">GEMINI_API_KEY not set. Add it to your .env file to enable AI reports.</div>',
                unsafe_allow_html=True,
            )
        else:
            with st.spinner("Generating AI report…"):
                raw = ai_svc.generate_health_report(
                    product_name   = product.get("name", ""),
                    ingredients    = product.get("ingredients_text", ""),
                    nutrients_json = json.dumps({k: v for k, v in nutrients.items() if v is not None}),
                    additive_json  = json.dumps(additives),
                    ban_json       = json.dumps(bans),
                    user_type      = user_type,
                )
            html = ai_svc.format_report_html(raw)
            st.markdown(f'<div class="card">{html}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────
def main():
    _inject_styles()

    # Services (instantiated once per session)
    product_svc  = ProductService()
    additive_svc = AdditiveService()
    ban_svc      = ProductBanService()
    scorer       = ScoringEngine()
    ai_svc       = AIService()

    # Session state
    for key, val in [("product", None), ("history", []), ("pending_barcode", None)]:
        if key not in st.session_state:
            st.session_state[key] = val

    # ── Sidebar ───────────────────────────────
    with st.sidebar:
        st.markdown('<p class="section-title">User Profile</p>', unsafe_allow_html=True)
        user_type = st.selectbox(
            "Who is consuming this?",
            ["General Adult", "Child", "Diabetic", "Pregnant", "Heart Patient"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.markdown('<p class="section-title">Recent Scans</p>', unsafe_allow_html=True)
        if st.session_state.history:
            for idx, h in enumerate(st.session_state.history[:6]):
                score = h.get("_concern_score", 0)
                if st.button(
                    f"{h.get('name','Unknown')[:22]} · {score}",
                    key=f"hist_{idx}",
                    use_container_width=True,
                ):
                    st.session_state.product = h
                    st.rerun()
        else:
            st.caption("No recent scans.")
        if st.session_state.history and st.button("Clear History", use_container_width=True):
            st.session_state.history = []
            st.session_state.product = None
            st.rerun()
        st.markdown("---")
        st.caption("Data: OpenFoodFacts · USDA FoodData Central · Gemini AI")

    # ── Header ────────────────────────────────
    st.markdown("""
    <div class="app-header">
      <h1>🛡️ Food Safety Intelligence</h1>
      <p>Real-time product analysis · Additive risk detection · AI health assessment</p>
    </div>
    """, unsafe_allow_html=True)

    # ────────────────────────────────────────────────────────────────────────
    # INPUT SECTION — two tabs: Camera Scanner  |  Manual Entry
    # Both call _process_barcode() and store result in st.session_state.product
    # ────────────────────────────────────────────────────────────────────────
    tab_camera, tab_manual = st.tabs(["📷 Camera Scanner", "⌨️ Manual Entry"])

    # ── TAB 1: Camera / WebRTC barcode scanner ────────────────────────────
    with tab_camera:
        if not WEBRTC_AVAILABLE:
            st.markdown(
                '<div class="warn-banner">'
                "Camera scanning requires <code>streamlit-webrtc</code>, <code>opencv-contrib-python</code> "
                "(or <code>pyzbar</code>), and <code>av</code>.<br>"
                "Install them and restart the app, or use Manual Entry instead."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="scanner-box">', unsafe_allow_html=True)
            st.markdown("### 📷 Point camera at a barcode")
            st.caption("Detection is automatic — the product will load the moment a barcode is recognised.")

            ctx = webrtc_streamer(
                key                    = "barcode_scanner",
                mode                   = WebRtcMode.SENDRECV,
                rtc_configuration      = RTC_CONFIGURATION,
                video_processor_factory= BarcodeScanner,
                media_stream_constraints={"video": True, "audio": False},
                async_processing       = True,
            )

            # Poll the video processor for a detected barcode
            if ctx.video_processor:
                with ctx.video_processor.lock:
                    detected = ctx.video_processor.detected_barcode
                    if detected:
                        ctx.video_processor.detected_barcode = None  # consume immediately

                if detected:
                    st.markdown(
                        f'<div class="success-banner">✅ Barcode detected: <strong>{detected}</strong> — fetching…</div>',
                        unsafe_allow_html=True,
                    )
                    with st.spinner("Fetching product…"):
                        product = _process_barcode(detected, product_svc, additive_svc, ban_svc, scorer)

                    if product:
                        st.session_state.product = product
                        barcodes = [h.get("barcode") for h in st.session_state.history]
                        if detected not in barcodes:
                            st.session_state.history.insert(0, product)
                            st.session_state.history = st.session_state.history[:10]
                        st.rerun()
                    else:
                        st.markdown(
                            f'<div class="warn-banner">Product not found for barcode <strong>{detected}</strong>. Try another product.</div>',
                            unsafe_allow_html=True,
                        )

            st.markdown("</div>", unsafe_allow_html=True)

    # ── TAB 2: Manual barcode entry ───────────────────────────────────────
    with tab_manual:
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            barcode_input = st.text_input(
                "barcode",
                placeholder="Enter barcode (e.g. 3017620422003) or product UPC…",
                label_visibility="collapsed",
            )
        with col_btn:
            search_clicked = st.button("Analyse", use_container_width=True)

        st.caption("Try: 3017620422003 (Nutella) · 737628064502 (Kettle Chips) · 041196910759 (Cheerios)")

        if search_clicked and barcode_input.strip():
            code = barcode_input.strip()
            with st.spinner("Fetching product data…"):
                product = _process_barcode(code, product_svc, additive_svc, ban_svc, scorer)

            if product:
                st.session_state.product = product
                barcodes = [h.get("barcode") for h in st.session_state.history]
                if code not in barcodes:
                    st.session_state.history.insert(0, product)
                    st.session_state.history = st.session_state.history[:10]
                st.rerun()
            else:
                st.markdown(
                    '<div class="warn-banner">Product not found. Check the barcode and try again.</div>',
                    unsafe_allow_html=True,
                )

    # ── Product display (shared, appears below both tabs) ─────────────────
    if st.session_state.product:
        _render_product(st.session_state.product, scorer, ai_svc, user_type)
    else:
        st.markdown("""
        <div style="text-align:center;padding:4rem 0;color:#6e7681">
          <div style="font-size:3rem;margin-bottom:1rem">🔍</div>
          <p style="font-size:1rem;color:#8b949e">Scan a barcode with your camera or enter one manually above</p>
          <p style="font-size:0.8rem">Concern score · Additive risks · Ban status · AI health report</p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()