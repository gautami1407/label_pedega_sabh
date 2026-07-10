import google.generativeai as genai
from PIL import Image
import io
import json
import re
import logging
import os
import time
import hashlib
import requests
from dotenv import load_dotenv
from csv_loader import RegulatoryCSVDatabase
from lps.shared.language import (
    MEDICAL_DISCLAIMER,
    WARNING_TEMPLATES,
    attention_label_from_score,
    attention_level_from_score,
    sanitize_warning_text,
)
from lps.services.news.service import NewsRecallService

# ── Environment Setup ─────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, ".env")

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    curr_path = script_dir
    while curr_path != os.path.dirname(curr_path):
        potential_dotenv = os.path.join(curr_path, ".env")
        if os.path.exists(potential_dotenv):
            dotenv_path = potential_dotenv
            break
        curr_path = os.path.dirname(curr_path)
    if dotenv_path:
        load_dotenv(dotenv_path)
    else:
        load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
USDA_API_KEY   = os.getenv("USDA_API_KEY", "")

# Try secrets.toml fallback
try:
    import toml
    secrets_path = os.path.join(script_dir, "secrets.toml")
    if os.path.exists(secrets_path):
        with open(secrets_path, "r") as f:
            secrets = toml.load(f)
            if "general" in secrets:
                if not GEMINI_API_KEY:
                    GEMINI_API_KEY = secrets["general"].get("gemini_api_key", "")
                if not USDA_API_KEY:
                    USDA_API_KEY = secrets["general"].get("usda_api_key", "")
except Exception:
    pass

try:
    from lps.shared.cache.product_cache import ProductCache
    _PRODUCT_CACHE = ProductCache()
except ImportError:
    _PRODUCT_CACHE = None

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".product_checker_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════
# DATA FETCHER — Open Food Facts + USDA
# ═══════════════════════════════════════════════════════
class DataFetcher:
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'LPSProductAnalyzer/3.0'})
        self.usda_key = USDA_API_KEY
        self._cache = _PRODUCT_CACHE

    def _cache_path(self, key, src):
        h = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{src}_{h}.json")

    def _load_cache(self, key, src, max_age=86400):
        if self._cache:
            cached = self._cache.get(key, src)
            if cached is not None:
                return cached
        p = self._cache_path(key, src)
        if os.path.exists(p):
            try:
                with open(p) as f:
                    c = json.load(f)
                if time.time() - c.get('cache_time', 0) <= max_age:
                    return c.get('data')
            except Exception:
                pass
        return None

    def _save_cache(self, key, src, data):
        if self._cache:
            self._cache.set(key, src, data)
        p = self._cache_path(key, src)
        try:
            with open(p, 'w') as f:
                json.dump({'data': data, 'cache_time': time.time()}, f)
        except Exception:
            pass

    def fetch_from_open_food_facts(self, barcode):
        cached = self._load_cache(barcode, 'off')
        if cached:
            return cached
        try:
            r = self.session.get(
                f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json",
                timeout=10
            )
            data = r.json()
            if data.get("status") == 1:
                self._save_cache(barcode, 'off', data)
                return data
            return None
        except Exception:
            return None

    def search_by_name(self, name, page_size=5):
        """Search Open Food Facts by product name."""
        cached = self._load_cache(f"search_{name}", 'off_search')
        if cached:
            return cached
        try:
            r = self.session.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={
                    "search_terms": name,
                    "json": 1,
                    "page_size": page_size,
                    "fields": "code,product_name,brands,image_small_url,nutriscore_grade,nova_group"
                },
                timeout=10
            )
            data = r.json()
            results = data.get("products", [])
            self._save_cache(f"search_{name}", 'off_search', results)
            return results
        except Exception:
            return []

    def fetch_from_usda(self, barcode):
        if not self.usda_key:
            return None
        cached = self._load_cache(barcode, 'usda')
        if cached:
            return cached
        try:
            r = self.session.get(
                "https://api.nal.usda.gov/fdc/v1/foods/search",
                params={"api_key": self.usda_key, "query": barcode, "pageSize": 1},
                timeout=10
            )
            search = r.json()
            if not search.get("foods"):
                return None
            fid = search["foods"][0]["fdcId"]
            r_detail = self.session.get(
                f"https://api.nal.usda.gov/fdc/v1/food/{fid}",
                params={"api_key": self.usda_key},
                timeout=10
            )
            detail = r_detail.json()
            combined = {"search_result": search, "detail": detail}
            self._save_cache(barcode, 'usda', combined)
            return combined
        except Exception:
            return None


# ═══════════════════════════════════════════════════════
# MAIN ANALYZER
# ═══════════════════════════════════════════════════════
class Analyzer:
    PROCESSING_LEVELS = {
        1: "Unprocessed or minimally processed",
        2: "Processed culinary ingredients",
        3: "Processed foods",
        4: "Ultra-processed food products"
    }

    NUTRISCORE_LABELS = {
        "a": "Excellent nutritional quality",
        "b": "Good nutritional quality",
        "c": "Average nutritional quality",
        "d": "Poor nutritional quality",
        "e": "Bad nutritional quality"
    }

    def __init__(self, model_name=None):
        model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.api_key = GEMINI_API_KEY
        if not self.api_key:
            logging.warning("GEMINI_API_KEY not found! AI insights will fallback to heuristics.")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)
        self.logger = logging.getLogger(__name__)
        self.reg_db = RegulatoryCSVDatabase()
        self.fetcher = DataFetcher()
        self.news_service = NewsRecallService()

    def _build_six_factor_payload(self, insights, product_data):
        """Normalize dashboard insights to the required six-factor workflow keys."""
        regulatory_status = insights.get("global_regulatory_status", [])
        ingredient_purpose = insights.get("ingredient_purpose", [])
        personal_warnings = insights.get("personal_warnings", [])
        additive_context = insights.get("additive_context", {})

        score = insights.get("concern_score", 0)
        return {
            "concern_score": score,
            "attention_level": attention_level_from_score(score),
            "attention_label": attention_label_from_score(score),
            "ingredient_purpose_analysis": ingredient_purpose,
            "global_regulatory_comparison": regulatory_status,
            "chemical_context_explanation": {
                "summary": "Plain-language additive context generated from detected ingredient patterns.",
                "categories": additive_context
            },
            "personalized_user_warnings": personal_warnings,
            "verified_news_and_recalls": self.news_service.get(
                product_name=product_data.get("name", ""),
                barcode=product_data.get("barcode", "")
            ).dict(),
            "disclaimer": MEDICAL_DISCLAIMER,
        }

    # ── Barcode Analysis ──────────────────────────────
    def analyze_barcode(self, barcode, user_preferences=None):
        """Fetch data and analyze a product via barcode."""
        off_data = self.fetcher.fetch_from_open_food_facts(barcode)

        result = None
        if off_data:
            result = self._format_off_data(off_data)
        else:
            usda_data = self.fetcher.fetch_from_usda(barcode)
            if usda_data:
                result = self._format_usda_data(usda_data)

        if result:
            result['dashboard_insights'] = self.generate_dashboard_insights(result, user_preferences)
            return result

        return {"error": "Product not found in databases"}

    # ── Deep OFF Data Extraction ──────────────────────
    def _format_off_data(self, data):
        """Extract comprehensive data from Open Food Facts response."""
        p = data["product"]
        name = p.get("product_name", "Unknown Product")
        brand = p.get("brands", "Unknown Brand")
        ingredients = p.get("ingredients_text", "Not available")
        additives_tags = p.get("additives_tags", [])

        # Nutrient data
        nutriments = p.get("nutriments", {})
        nutrient_levels = p.get("nutrient_levels", {})

        # OFF Scores
        nutriscore = p.get("nutriscore_grade") or p.get("nutrition_grades") or "unknown"
        nova = p.get("nova_group") or "unknown"
        ecoscore = p.get("ecoscore_grade") or "unknown"

        # Categories & Labels
        categories = p.get("categories_tags", [])
        category_display = categories[0].replace("en:", "").replace("-", " ").capitalize() if categories else "Unknown"
        labels = [lbl.replace("en:", "").replace("-", " ") for lbl in p.get("labels_tags", [])]

        # Allergens from OFF
        allergens = [a.replace("en:", "") for a in p.get("allergens_tags", [])]
        allergens_text = p.get("allergens", "")

        # Additives cleaned
        additives_clean = [add.replace("en:", "").upper() for add in additives_tags]

        # Ingredients analysis tags
        ingredients_analysis = [ia.replace("en:", "") for ia in p.get("ingredients_analysis_tags", [])]

        # CSV Regulatory cross-check
        csv_regulatory = self.reg_db.get_global_regulatory_status(ingredients)
        detailed_additives = self.reg_db.get_detailed_additive_report(ingredients, additives_tags)

        # Identify banned ingredients
        banned_ingredients = []
        for add in detailed_additives:
            for country, status in add.get('country_status', {}).items():
                if 'banned' in status.lower():
                    banned_ingredients.append({
                        "ingredient": add['name'],
                        "e_number": add['e_number'],
                        "banned_in": [c for c, s in add['country_status'].items() if 'banned' in s.lower()],
                        "reason": add.get('reason', ''),
                        "risk_level": add.get('risk_level', 'High')
                    })
                    break

        # Nutrition analysis with daily value percentages
        nutrition_analysis = self._compute_nutrition_analysis(nutriments)

        # Sustainability from OFF
        sustainability = {
            "ecoscore": ecoscore,
            "ecoscore_label": self._ecoscore_label(ecoscore),
            "packaging": p.get("packaging", "Not specified"),
            "origins": p.get("origins", "Not specified"),
            "manufacturing_places": p.get("manufacturing_places", "Not specified"),
        }

        return {
            "name": name,
            "brand": brand,
            "category": category_display,
            "ingredients": ingredients,
            "nutrition": nutriments,
            "nutrition_analysis": nutrition_analysis,
            "nutrient_levels": nutrient_levels,
            "scores": {
                "nutriscore": nutriscore,
                "nutriscore_label": self.NUTRISCORE_LABELS.get(nutriscore, "Unknown"),
                "nova": nova,
                "nova_label": self.PROCESSING_LEVELS.get(int(nova) if str(nova).isdigit() else 0, "Unknown"),
                "ecoscore": ecoscore,
                "ecoscore_label": self._ecoscore_label(ecoscore),
            },
            "allergens": allergens,
            "allergens_text": allergens_text,
            "additives": additives_clean,
            "additives_tags": additives_tags,
            "ingredients_analysis": ingredients_analysis,
            "labels": labels,
            "image": p.get("image_url"),
            "detailed_additives": detailed_additives,
            "regulatory": {
                "banned_ingredients": banned_ingredients,
                "csv_global_status": csv_regulatory,
            },
            "sustainability": sustainability,
        }

    def _ecoscore_label(self, grade):
        labels = {
            "a": "Very low environmental impact",
            "b": "Low environmental impact",
            "c": "Moderate environmental impact",
            "d": "High environmental impact",
            "e": "Very high environmental impact",
        }
        return labels.get(str(grade).lower(), "Not assessed")

    def _compute_nutrition_analysis(self, nutriments):
        """Compute daily value percentages from nutriments."""
        # Daily reference values (adults)
        daily_ref = {
            "energy-kcal": 2000,
            "fat": 65,
            "saturated-fat": 20,
            "carbohydrates": 300,
            "sugars": 50,
            "fiber": 25,
            "proteins": 50,
            "salt": 6,
            "sodium": 2.4,
        }

        analysis = {}
        for key, daily in daily_ref.items():
            val_100g = nutriments.get(f"{key}_100g")
            if val_100g is not None:
                try:
                    val = float(val_100g)
                    pct = round((val / daily) * 100, 1)
                    analysis[key] = {
                        "per_100g": round(val, 1),
                        "daily_pct": min(pct, 999),
                        "level": "high" if pct > 25 else ("moderate" if pct > 10 else "low")
                    }
                except (ValueError, TypeError):
                    pass

        return analysis

    # ── USDA Fallback ─────────────────────────────────
    def _format_usda_data(self, data):
        search = data.get("search_result", {})
        detail = data.get("detail", {})
        food = search["foods"][0]
        name = food.get("description", "Unknown")
        brand = food.get("brandOwner", "Unknown Brand")
        ingredients = detail.get("ingredients", "Not available")

        return {
            "name": name,
            "brand": brand,
            "category": food.get("foodCategory", "Unknown"),
            "ingredients": ingredients,
            "nutrition": detail.get("foodNutrients", []),
            "nutrition_analysis": {},
            "nutrient_levels": {},
            "scores": {"nutriscore": "unknown", "nova": "unknown", "ecoscore": "unknown"},
            "allergens": [],
            "additives": [],
            "additives_tags": [],
            "labels": [],
            "image": None,
            "detailed_additives": self.reg_db.get_detailed_additive_report(ingredients),
            "regulatory": {
                "banned_ingredients": [],
                "csv_global_status": self.reg_db.get_global_regulatory_status(ingredients),
            },
            "sustainability": {},
        }

    # ── Image Analysis ────────────────────────────────
    def analyze_image(self, image_bytes, user_preferences=None):
        if user_preferences is None:
            user_preferences = {'dietary': [], 'allergies': [], 'health_goals': [], 'health_conditions': []}

        PROMPT_TEMPLATE = """
Analyze this food product label image and provide high-fidelity JSON. Identify the product, brand, category, ingredients, and nutrition data.
Be extremely accurate with the text extraction. Do NOT perform any regulatory assessment—only extract the data from the image.

Format:
{
  "name": "Product Name",
  "brand": "Brand Name",
  "category": "Category",
  "ingredients": "Comma separated list...",
  "nutrition": {"energy-kcal_100g": 0, "proteins_100g": 0, "carbohydrates_100g": 0, "fat_100g": 0, "sugars_100g": 0, "salt_100g": 0, "fiber_100g": 0, "saturated-fat_100g": 0},
  "allergens": ["list"],
  "processing_level": "Highly processed",
  "health_impact": "Concerning",
  "sustainability": {
    "score": 65,
    "carbon_footprint": "Medium",
    "packaging": "Plastic - Recyclable",
    "tips": ["Buy in bulk to reduce waste"]
  },
  "storage_tips": "Store in a cool, dry place."
}
"""
        try:
            for attempt in range(4):
                try:
                    response = self.model.generate_content([
                        PROMPT_TEMPLATE,
                        {"mime_type": "image/jpeg", "data": image_bytes}
                    ])
                    json_match = re.search(r'```json\s*(.*?)\s*```', response.text, re.DOTALL)
                    json_str = json_match.group(1) if json_match else response.text
                    result = json.loads(json_str.strip())

                    # Apply deterministic regulatory checks from CSV
                    ingredients = result.get('ingredients', '')
                    result['regulatory'] = {
                        "banned_ingredients": [],
                        "csv_global_status": self.reg_db.get_global_regulatory_status(ingredients),
                    }
                    result['detailed_additives'] = self.reg_db.get_detailed_additive_report(ingredients)

                    # Check for banned
                    for add in result['detailed_additives']:
                        for country, status in add.get('country_status', {}).items():
                            if 'banned' in status.lower():
                                result['regulatory']['banned_ingredients'].append({
                                    "ingredient": add['name'],
                                    "e_number": add['e_number'],
                                    "banned_in": [c for c, s in add['country_status'].items() if 'banned' in s.lower()],
                                    "reason": add.get('reason', ''),
                                })
                                break

                    # Compute nutrition analysis
                    result['nutrition_analysis'] = self._compute_nutrition_analysis(result.get('nutrition', {}))
                    result['scores'] = result.get('scores', {"nutriscore": "unknown", "nova": "unknown", "ecoscore": "unknown"})

                    # Generate dashboard insights
                    result['dashboard_insights'] = self.generate_dashboard_insights(result, user_preferences)
                    return result

                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                        if attempt < 3:
                            time.sleep(2 ** attempt)
                            continue
                    raise e
        except Exception as e:
            self.logger.error(f"Image analysis error: {e}")
            return {"error": str(e)}

    # ── AI Dashboard Insights ─────────────────────────
    def generate_dashboard_insights(self, product_data, user_preferences=None):
        """Generate comprehensive AI insights with full personal profile integration."""
        profile_context = ""
        if user_preferences:
            # Build BMI context
            bmi_context = ""
            try:
                height_cm = float(user_preferences.get('height', 0))
                weight_kg = float(user_preferences.get('weight', 0))
                if height_cm > 0 and weight_kg > 0:
                    bmi = weight_kg / ((height_cm / 100) ** 2)
                    bmi_cat = (
                        "underweight" if bmi < 18.5 else
                        "normal weight" if bmi < 25 else
                        "overweight" if bmi < 30 else "obese"
                    )
                    bmi_context = f"BMI: {bmi:.1f} ({bmi_cat})"
            except (ValueError, TypeError):
                pass

            allergies_list = user_preferences.get('allergies', [])
            if isinstance(allergies_list, str):
                allergies_list = [a.strip() for a in allergies_list.split(',')]
            allergies_str = ', '.join(allergies_list) if allergies_list else 'None declared'

            profile_context = f"""
User Health Profile (STRICTLY personalize personal_warnings based on this):
- Age: {user_preferences.get('age', 'N/A')}
- {bmi_context if bmi_context else f"Height: {user_preferences.get('height', 'N/A')}cm, Weight: {user_preferences.get('weight', 'N/A')}kg"}
- Diet: {user_preferences.get('dietaryPreference', 'N/A')}
- Allergies: {allergies_str}
- Other sensitivities: {user_preferences.get('sensitivities', 'None')}
- Other allergy detail: {user_preferences.get('otherAllergy', 'None')}

PERSONALIZATION RULES for personal_warnings (use liability-safe language only):
1. If ANY ingredient matches user allergies → high attention warning (never say danger/unsafe/critical)
2. If product contains animal-derived ingredients and user is vegetarian/vegan → high attention warning
3. If user is diabetic-friendly and product has high sugar → high attention warning
4. If user age < 12 and product has caffeine or artificial colors → moderate attention warning
5. If BMI > 30 and product is high calorie → moderate attention warning
6. NEVER use words: danger, critical, unsafe, dangerous, toxic, do not consume
7. Use phrasing like "worth your attention", "you may wish to review", "may be relevant to your profile"
"""

        PROMPT_TEMPLATE = """
You are a food safety expert AI. Analyze this packaged food product data thoroughly.

Product Data:
{PRODUCT_DATA_JSON}

{PROFILE_CONTEXT}

Return ONLY a valid JSON object (no markdown, no extra text) matching this EXACT schema:
{
  "concern_score": 72,
  "ingredient_purpose": [
    {"name": "Exact Ingredient Name", "purpose": "Plain-language explanation of its role and any health concerns", "risk_level": "Safe|Moderate|High"}
  ],
  "additive_context": {
    "preservatives": <integer count>,
    "colorants": <integer count>,
    "flavors_msg": <integer count>,
    "stabilizers": <integer count>
  },
  "global_regulatory_status": [],
  "personal_warnings": [
    {"type": "high|moderate", "title": "Short Attention Title", "description": "Brief informational notice using liability-safe language"}
  ],
  "healthier_alternatives": [
    {"name": "Alternative Name", "description": "Why it's healthier", "benefit": "Key nutritional benefit"}
  ],
  "certifications": ["list of detected certifications or 'None verified'"],
  "allergens_analysis": "Brief allergen summary sentence.",
  "processing_level": "Highly processed",
  "health_impact": "Concerning",
  "sustainability": {
    "score": 65,
    "carbon_footprint": "Medium",
    "packaging": "Plastic",
    "tips": ["tip 1"]
  },
  "storage_tips": "description",
  "shelf_life_impact": "Brief sentence about preservatives and shelf life."
}
Guidelines: concern_score 0-100 (higher = more factors worth attention). Be accurate based on real ingredient data.
Never declare products safe or unsafe. Use informational language only. Generate at least 3 alternative product suggestions.
"""
        final_prompt = PROMPT_TEMPLATE.replace("{PRODUCT_DATA_JSON}", json.dumps(product_data, default=str))
        final_prompt = final_prompt.replace("{PROFILE_CONTEXT}", profile_context)

        try:
            for attempt in range(4):
                try:
                    response = self.model.generate_content(final_prompt)
                    raw = response.text.strip()
                    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
                    json_str = json_match.group(1) if json_match else raw
                    json_str = re.sub(r'^[^{\[]+', '', json_str)
                    parsed = json.loads(json_str)

                    # Ensure required fields
                    if 'additive_context' in parsed and 'flavors_msg' not in parsed['additive_context']:
                        parsed['additive_context']['flavors_msg'] = 0

                    # Deterministic Regulatory Overwrite from CSV
                    ingredients_text = product_data.get('ingredients', '')
                    csv_status = product_data.get('regulatory', {}).get('csv_global_status')
                    if csv_status:
                        parsed['global_regulatory_status'] = csv_status
                    else:
                        parsed['global_regulatory_status'] = self.reg_db.get_global_regulatory_status(ingredients_text)

                    # Bump concern score if banned ingredients found
                    banned = product_data.get('regulatory', {}).get('banned_ingredients', [])
                    if banned:
                        parsed['concern_score'] = max(95, parsed.get('concern_score', 0))

                    # Ensure healthier_alternatives exists
                    if 'healthier_alternatives' not in parsed:
                        parsed['healthier_alternatives'] = []

                    parsed = self._sanitize_insights(parsed)
                    parsed["six_factor_engine"] = self._build_six_factor_payload(parsed, product_data)
                    parsed["disclaimer"] = MEDICAL_DISCLAIMER
                    return parsed

                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                        if attempt < 3:
                            time.sleep(2 ** attempt)
                            continue
                    raise e

        except Exception as e:
            self.logger.error(f"Error generating insights: {e}")
            fallback = self._generate_fallback_insights(product_data, user_preferences)
            fallback = self._sanitize_insights(fallback)
            fallback["six_factor_engine"] = self._build_six_factor_payload(fallback, product_data)
            fallback["disclaimer"] = MEDICAL_DISCLAIMER
            return fallback

    def _sanitize_insights(self, insights: dict) -> dict:
        """Enforce liability-safe language on all warning output."""
        warnings = insights.get("personal_warnings", [])
        for warning in warnings:
            warning_type = warning.get("type", "")
            if warning_type == "red":
                warning["type"] = "high"
            elif warning_type == "orange":
                warning["type"] = "moderate"
            warning["title"] = sanitize_warning_text(warning.get("title", ""))
            warning["description"] = sanitize_warning_text(warning.get("description", ""))
        insights["personal_warnings"] = warnings
        return insights

    # ── Deterministic Fallback ────────────────────────
    def _generate_fallback_insights(self, product_data, user_preferences=None):
        """Deterministic fallback when AI is unavailable."""
        score = 50
        warnings = []
        add_ctx = {"preservatives": 0, "colorants": 0, "stabilizers": 0, "flavors_msg": 0}
        ing_purpose = []

        # Calculate from OFF scores
        scores = product_data.get("scores", {})
        nutri = scores.get("nutriscore", "unknown")
        nova = scores.get("nova", "unknown")

        if str(nova) == "4": score = max(score, 80)
        elif str(nova) == "3": score = max(score, 60)
        elif str(nova) == "1": score = min(score, 20)

        if nutri == "e": score = max(score, 85)
        elif nutri == "d": score = max(score, 70)
        elif nutri == "a": score = min(score, 10)

        # Banned ingredients
        reg = product_data.get("regulatory", {})
        banned = reg.get("banned_ingredients", [])
        if banned:
            score = 95
            for b in banned:
                tmpl = WARNING_TEMPLATES["regulatory_restriction"]
                jurisdictions = ", ".join(b.get("banned_in", [])) or "one or more jurisdictions"
                warnings.append({
                    "type": "high",
                    "title": tmpl["title"].format(ingredient=b.get("ingredient", "Unknown")),
                    "description": tmpl["description"].format(
                        ingredient=b.get("ingredient", "Unknown"),
                        jurisdictions=jurisdictions,
                        reason=b.get("reason", "See regulatory database for details."),
                    ),
                })
                ing_purpose.append({
                    "name": b.get("ingredient", "Unknown"),
                    "purpose": b.get("reason", "Unknown risk"),
                    "risk_level": "High"
                })

        # Allergen cross-check with user profile
        allergens = product_data.get("allergens", [])
        user_allergies = []
        if user_preferences:
            raw_allergies = user_preferences.get('allergies', [])
            if isinstance(raw_allergies, str):
                raw_allergies = [a.strip() for a in raw_allergies.split(',')]
            user_allergies = [a.lower() for a in raw_allergies if a and a != 'none']

            # Diet check
            diet = (user_preferences.get('dietaryPreference', '') or '').lower()
            ingredients_lower = (product_data.get('ingredients', '') or '').lower()
            analysis_tags = product_data.get('ingredients_analysis', [])

            if diet in ('vegan', 'vegetarian'):
                non_veg_indicators = ['non-vegan', 'non-vegetarian', 'may-contain-meat']
                for tag in analysis_tags:
                    if any(ind in tag.lower() for ind in non_veg_indicators):
                        tmpl = WARNING_TEMPLATES["diet_mismatch"]
                        warnings.append({
                            "type": "high",
                            "title": tmpl["title"],
                            "description": tmpl["description"].format(diet=diet.capitalize())
                                + f" Detected tag: {tag}.",
                        })
                        score = max(score, 85)
                        break

            if diet == 'diabetic-friendly':
                sugar_level = product_data.get('nutrient_levels', {}).get('sugars', '')
                if sugar_level == 'high':
                    tmpl = WARNING_TEMPLATES["sugar_attention"]
                    warnings.append({
                        "type": "high",
                        "title": tmpl["title"],
                        "description": tmpl["description"],
                    })
                    score = max(score, 80)

        for al in allergens:
            al_lower = al.lower()
            is_match = any(ua in al_lower or al_lower in ua for ua in user_allergies)

            if is_match:
                tmpl = WARNING_TEMPLATES["allergen_profile_match"]
                warnings.append({
                    "type": "high",
                    "title": tmpl["title"],
                    "description": tmpl["description"].format(allergen=al.capitalize()),
                })
                score = min(100, score + 40)
            else:
                tmpl = WARNING_TEMPLATES["allergen_present"]
                warnings.append({
                    "type": "moderate",
                    "title": tmpl["title"].format(allergen=al.capitalize()),
                    "description": tmpl["description"].format(allergen=al.capitalize()),
                })

        # Additive counting from ingredients text
        ingredients_text = str(product_data.get("ingredients", "")).lower()

        preservative_keys = ["preservative", "benzoate", "sorbate", "propionate", "nitrate", "nitrite", "sulfite", "e200", "e211", "e202", "e250", "e220"]
        add_ctx["preservatives"] = sum(1 for k in preservative_keys if k in ingredients_text)

        colorant_keys = ["colour", "color", "caramel", "e150", "e102", "e110", "e124", "e129", "tartrazine", "red 40", "yellow 5", "sunset yellow", "brilliant blue"]
        add_ctx["colorants"] = sum(1 for k in colorant_keys if k in ingredients_text)

        stabilizer_keys = ["gum", "pectin", "lecithin", "e471", "e472", "e481", "e322", "carrageenan", "xanthan", "cellulose", "starch"]
        add_ctx["stabilizers"] = sum(1 for k in stabilizer_keys if k in ingredients_text)

        flavor_keys = ["flavor", "flavour", "msg", "monosodium", "glutamate", "e621", "e627", "e631", "diacetyl", "artificial"]
        add_ctx["flavors_msg"] = sum(1 for k in flavor_keys if k in ingredients_text)

        # Basic ingredient purpose
        if not ing_purpose:
            ings = [i.strip() for i in ingredients_text.split(',')]
            count = 0
            for i in ings:
                if count >= 5:
                    break
                if not i or i == "not available":
                    continue
                risk = "Safe"
                if any(k in i for k in ["sugar", "palm oil", "sodium"]):
                    risk = "Moderate"
                ing_purpose.append({
                    "name": i.capitalize(),
                    "purpose": "Standard ingredient component",
                    "risk_level": risk
                })
                count += 1

        # Regulatory status from CSV
        csv_status = reg.get('csv_global_status')
        if not csv_status:
            csv_status = self.reg_db.get_global_regulatory_status(ingredients_text)

        # Healthier alternatives
        alternatives = [
            {"name": "Whole grain version", "description": "Opt for whole grain alternatives with less processing", "benefit": "More fiber, less additives"},
            {"name": "Organic equivalent", "description": "Organic versions use fewer synthetic additives", "benefit": "No artificial preservatives"},
            {"name": "Homemade alternative", "description": "Making it at home gives full control over ingredients", "benefit": "No hidden additives"}
        ]

        return {
            "concern_score": score,
            "ingredient_purpose": ing_purpose,
            "additive_context": add_ctx,
            "global_regulatory_status": csv_status,
            "allergens_analysis": "Contains: " + (", ".join(allergens) if allergens else "None declared. Check packaging."),
            "healthier_alternatives": alternatives,
            "certifications": product_data.get("labels", ["Cannot verify automatically"]),
            "personal_warnings": warnings,
            "processing_level": product_data.get("scores", {}).get("nova_label", "Unknown"),
            "health_impact": "Concerning" if score > 60 else ("Neutral" if score > 30 else "Beneficial"),
            "sustainability": product_data.get("sustainability", {}),
            "storage_tips": "Store in a cool, dry place away from direct sunlight.",
            "shelf_life_impact": "Check packaging for best-before date."
        }

    # ── AI Chat ───────────────────────────────────────
    def chat_with_assistant(self, query, context_data=None):
        product_info = ""
        if context_data:
            name = context_data.get('name', 'this product')
            brand = context_data.get('brand', '')
            ingredients = context_data.get('ingredients', 'Not available')
            scores = context_data.get('scores', {})
            allergens = context_data.get('allergens', [])
            product_info = (
                f"Product: {name} by {brand}\n"
                f"Ingredients: {ingredients}\n"
                f"Nutri-Score: {scores.get('nutriscore', 'N/A')}, NOVA: {scores.get('nova', 'N/A')}\n"
                f"Allergens: {', '.join(allergens) if allergens else 'None declared'}\n"
            )

        chat_prompt = (
            f"You are LPS AI, an informational product label assistant for Label Padegha Sabh.\n"
            f"{product_info}\n"
            f"User question: {query}\n\n"
            f"Answer concisely in 2-4 sentences using plain language.\n"
            f"RULES: Never provide medical advice, diagnoses, or dosage recommendations. "
            f"Never use words: danger, critical, unsafe, dangerous, toxic. "
            f"Use informational phrasing like 'worth your attention' or 'you may wish to review'. "
            f"Reference the product data above when relevant. If unsure, say so.\n"
            f"End with: 'This is informational, not medical advice.'"
        )

        try:
            for attempt in range(4):
                try:
                    response = self.model.generate_content(chat_prompt)
                    return response.text
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                        if attempt < 3:
                            time.sleep(2 ** attempt)
                            continue
                    raise e
        except Exception as e:
            err_msg = str(e)
            if any(code in err_msg for code in ["429", "RESOURCE_EXHAUSTED", "quota", "rate"]):
                return (
                    "⚠️ I'm temporarily unavailable due to high usage (API quota limit reached). "
                    "The product analysis on your dashboard was already completed using OpenFoodFacts data. "
                    "Please try asking again in a minute!"
                )
            if any(code in err_msg for code in ["API_KEY_INVALID", "400", "403"]):
                return (
                    "🔑 The AI assistant is currently offline (invalid API key). "
                    "However, your product dashboard is fully populated with real data from OpenFoodFacts!"
                )
            return f"I ran into an issue. Please try again. ({err_msg[:80]})"
