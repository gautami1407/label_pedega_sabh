"""
Product Intelligence Analysis Engine v3
========================================
Complete 12-step pipeline:
1. Barcode -> OpenFoodFacts / USDA / CSV lookup
2. Ingredient explanation from knowledge base
3. Rule-based concern score (transparent, no AI)
4. Allergen detection
5. Personalized warnings (health profile)
6. Global regulatory status (8 countries)
7. Recall/news fetch (enhanced with ingredients/category)
8. NOVA classification
9. AI summary via Gemini (with rule-based fallback)
10. Related products for comparison
11. Better alternatives
12. Scientific references
"""

import os
import sys
import glob
import pandas as pd
import logging
from typing import List, Dict, Optional, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.product_lookup import lookup_product
from utils.data_processor import (
    normalize_product_data,
    parse_ingredients,
    merge_ingredients_and_additives,
    get_merged_ingredient_names,
)
from utils.risk_engine import load_banned_ingredients, check_banned_ingredients, calculate_health_score
from utils.dataset_regulatory_checker import check_ingredients_against_dataset
from news_service import get_safety_news

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
BANNED_DB_PATH = os.path.join(DATA_DIR, "banned_ingredients.csv")

# ── Auto-load every CSV in data/ ───────────────────────────
def _auto_load_csvs(data_dir):
    csvs = {}
    for fp in glob.glob(os.path.join(data_dir, "*.csv")):
        stem = os.path.splitext(os.path.basename(fp))[0]
        try:
            csvs[stem] = pd.read_csv(fp)
            logger.info(f"[CSV] Loaded {stem}.csv ({len(csvs[stem])} rows)")
        except Exception as e:
            logger.warning(f"[CSV] Could not load {fp}: {e}")
    return csvs

ALL_CSVS = _auto_load_csvs(DATA_DIR)

def _get_df(name):
    return ALL_CSVS.get(name)

# ── Build ingredient knowledge dict ───────────────────────
def _build_ingredient_knowledge():
    df = _get_df("ingredient_knowledge")
    if df is None or df.empty:
        return {}
    out = {}
    for _, row in df.iterrows():
        key = str(row.get("Ingredient", "")).strip().lower()
        if key:
            out[key] = {
                "purpose":      str(row.get("Purpose", "")),
                "simple_name":  str(row.get("SimpleName", "")),
                "health_notes": str(row.get("HealthNotes", "")),
                "category":     str(row.get("Category", ""))
            }
    return out

# ── Build regulations dict ────────────────────────────────
def _build_regulations():
    df = _get_df("regulations")
    if df is None or df.empty:
        return {}
    out = {}
    for _, row in df.iterrows():
        key = str(row.get("Ingredient", "")).strip().lower()
        if key:
            out[key] = {
                "fssai":     str(row.get("FSSAI", "Unknown")),
                "fda":       str(row.get("FDA", "Unknown")),
                "efsa":      str(row.get("EFSA", "Unknown")),
                "uk":        str(row.get("UK", "Unknown")),
                "canada":    str(row.get("Canada", "Unknown")),
                "australia": str(row.get("Australia", "Unknown")),
                "japan":     str(row.get("Japan", "Unknown")),
                "singapore": str(row.get("Singapore", "Unknown")),
                "notes":     str(row.get("Notes", ""))
            }
    return out

INGREDIENT_KNOWLEDGE = _build_ingredient_knowledge()
REGULATIONS_DATA     = _build_regulations()
BANNED_DF            = load_banned_ingredients(BANNED_DB_PATH)

# ── Allergen keyword map ──────────────────────────────────
ALLERGEN_KEYWORDS = {
    "Milk":      ["milk", "dairy", "cream", "cheese", "whey", "casein", "lactose", "butter", "yogurt", "ghee"],
    "Peanut":    ["peanut", "groundnut", "arachis"],
    "Tree Nut":  ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "macadamia"],
    "Egg":       ["egg", "eggs", "albumin", "ovalbumin", "lysozyme"],
    "Soy":       ["soy", "soya", "tofu", "edamame", "soybean", "soy lecithin"],
    "Wheat":     ["wheat", "gluten", "maida", "atta", "semolina", "durum", "spelt", "barley", "rye"],
    "Fish":      ["fish", "salmon", "tuna", "cod", "mackerel", "sardine", "anchovy"],
    "Shellfish": ["shrimp", "prawn", "crab", "lobster", "mussel", "clam", "oyster", "scallop"],
    "Sesame":    ["sesame", "til", "tahini", "gingelly"],
    "Mustard":   ["mustard", "mustard seed"],
    "Sulfite":   ["sulfite", "sulphite", "sulfur dioxide", "e220", "e221"],
}

ARTIFICIAL_COLOUR_KW     = ["red 40","yellow 5","yellow 6","blue 1","blue 2","allura red","tartrazine",
                             "sunset yellow","brilliant blue","indigotine","e102","e110","e129","e133","caramel colour"]
ARTIFICIAL_SWEETENER_KW  = ["aspartame","saccharin","sucralose","acesulfame","ace-k","neotame","e951","e952","e954","e955"]
ARTIFICIAL_PRESERVATIVE_KW = ["sodium benzoate","potassium sorbate","sodium nitrite","sodium nitrate","bha","bht",
                               "propyl gallate","tbhq","calcium propionate","e211","e202","e250","e320","e321"]
MSG_KW       = ["monosodium glutamate","msg","e621"]
PALM_OIL_KW  = ["palm oil","palm kernel oil","refined palm oil"]
TRANS_FAT_KW = ["partially hydrogenated","trans fat","hydrogenated vegetable"]

# ── Step 1-3: Product lookup ──────────────────────────────
def fetch_product_data(barcode):
    logger.info(f"[Fetch] barcode={barcode}")
    raw = lookup_product(barcode)
    if raw:
        logger.info(f"[Fetch] Found: {raw.get('name')} | source={raw.get('source')}")
        return normalize_product_data(raw)
    logger.warning(f"[Fetch] Not found: {barcode}")
    return None

# ── Step 4: Ingredient explanations ──────────────────────
def lookup_ingredient_explanations(ingredients, metadata=None):
    """
    Build per-ingredient explanation cards.
    `metadata` is the list of records from merge_ingredients_and_additives()
    — used to annotate source ("additives", "both") and INS/E numbers.
    """
    # Build a quick lookup from ingredient_name → metadata record
    meta_map = {}
    if metadata:
        for rec in metadata:
            meta_map[rec["ingredient_name"].strip().lower()] = rec

    results = []
    for ing in ingredients:
        il = ing.strip().lower()
        entry = INGREDIENT_KNOWLEDGE.get(il)
        if not entry:
            for key, val in INGREDIENT_KNOWLEDGE.items():
                if key in il or il in key:
                    entry = val
                    break

        meta_rec = meta_map.get(il, {})
        ins_e_label = ""
        if meta_rec.get("ins_number") or meta_rec.get("e_number"):
            parts = []
            if meta_rec.get("ins_number"): parts.append(meta_rec["ins_number"])
            if meta_rec.get("e_number"):   parts.append(meta_rec["e_number"])
            ins_e_label = "/".join(parts)

        if entry:
            results.append({
                "name":        ing,
                "simple_name": entry["simple_name"],
                "purpose":     entry["purpose"],
                "description": entry["health_notes"],
                "category":    entry["category"],
                "source":      meta_rec.get("source", "ingredients"),
                "ins_e":       ins_e_label,
            })
        else:
            results.append({
                "name":        ing,
                "simple_name": "",
                "purpose":     "Ingredient listed on label.",
                "description": "No verified public information available.",
                "category":    "Unknown",
                "source":      meta_rec.get("source", "ingredients"),
                "ins_e":       ins_e_label,
            })
    return results

# ── Step 5: Concern score ─────────────────────────────────
def compute_concern_score(nutriments, ingredients, risks, user_profile=None):
    score = 0
    factors = []
    ing_text = " ".join(i.lower() for i in ingredients)

    sugar    = float(nutriments.get("sugars_100g") or 0)
    salt_g   = float(nutriments.get("salt_100g") or 0)
    sat_fat  = float(nutriments.get("saturated-fat_100g") or 0)
    fiber    = float(nutriments.get("fiber_100g") or 0)
    energy   = float(nutriments.get("energy-kcal_100g") or nutriments.get("energy_100g") or 0)
    if energy > 900: energy = energy / 4.184  # kJ to kcal

    if sugar > 20:   score += 25; factors.append(f"Very High Sugar ({sugar:.1f}g/100g)")
    elif sugar > 15: score += 20; factors.append(f"High Sugar ({sugar:.1f}g/100g)")
    elif sugar > 10: score += 10; factors.append(f"Moderate Sugar ({sugar:.1f}g/100g)")

    if salt_g > 2.0:   score += 25; factors.append(f"Very High Sodium ({salt_g:.1f}g salt/100g)")
    elif salt_g > 1.5: score += 20; factors.append(f"High Sodium ({salt_g:.1f}g salt/100g)")
    elif salt_g > 0.6: score += 10; factors.append(f"Moderate Sodium ({salt_g:.1f}g salt/100g)")

    if sat_fat > 8:   score += 20; factors.append(f"Very High Saturated Fat ({sat_fat:.1f}g/100g)")
    elif sat_fat > 5: score += 15; factors.append(f"High Saturated Fat ({sat_fat:.1f}g/100g)")

    if energy > 500:  score += 10; factors.append(f"High Calorie ({energy:.0f} kcal/100g)")
    if fiber < 0.5 and len(ingredients) > 3: score += 5; factors.append("Very Low Fiber")

    if any(kw in ing_text for kw in ARTIFICIAL_COLOUR_KW):
        score += 10; factors.append("Contains Artificial Colours")
    if any(kw in ing_text for kw in ARTIFICIAL_SWEETENER_KW):
        score += 10; factors.append("Contains Artificial Sweeteners")
    if any(kw in ing_text for kw in ARTIFICIAL_PRESERVATIVE_KW):
        score += 10; factors.append("Contains Artificial Preservatives")
    if any(kw in ing_text for kw in MSG_KW):
        score += 8;  factors.append("Contains MSG")
    if any(kw in ing_text for kw in PALM_OIL_KW):
        score += 5;  factors.append("Contains Palm Oil")
    if any(kw in ing_text for kw in TRANS_FAT_KW):
        score += 20; factors.append("Contains Trans Fats (Partially Hydrogenated Oil)")

    for risk in risks:
        lvl  = str(risk.get("risk_level", "")).lower()
        name = risk.get("ingredient", "Unknown")
        if lvl == "high":   score += 15; factors.append(f"High-Risk Ingredient: {name}")
        elif lvl == "medium": score += 10; factors.append(f"Medium-Risk Ingredient: {name}")
        elif lvl == "low":    score += 5;  factors.append(f"Flagged Ingredient: {name}")

    if user_profile:
        for c in [x.lower() for x in user_profile.get("conditions", [])]:
            if "diabet" in c and sugar > 10:
                score += 20; factors.append("High Sugar — Risk for Diabetes")
            if ("hypertension" in c or "blood pressure" in c) and salt_g > 0.5:
                score += 20; factors.append("High Sodium — Risk for Hypertension")
            if "kidney" in c and salt_g > 0.3:
                score += 20; factors.append("Sodium — Concern for Kidney Disease")
            if ("pregnan" in c) and any(kw in ing_text for kw in ARTIFICIAL_COLOUR_KW):
                score += 20; factors.append("Artificial Colours — Pregnancy Concern")

    score = max(0, min(100, score))
    if score <= 20:   level = "Low Concern"
    elif score <= 45: level = "Moderate Concern"
    elif score <= 70: level = "High Concern"
    else:             level = "Very High Concern"
    return {"score": score, "level": level, "factors": factors[:12]}

# ── Step 6: Allergen detection ────────────────────────────
def detect_allergens(ingredients):
    detected, seen = [], set()
    for ing in ingredients:
        il = ing.strip().lower()
        for allergen, keywords in ALLERGEN_KEYWORDS.items():
            if allergen in seen: continue
            for kw in keywords:
                if kw in il:
                    detected.append({"allergen": allergen, "found_in": ing, "keyword_matched": kw,
                                     "risk": "High" if allergen in ["Peanut","Tree Nut","Shellfish","Egg"] else "Medium"})
                    seen.add(allergen)
                    break
    return detected

# ── Step 7: Personalized warnings ────────────────────────
def generate_personalized_warnings(nutriments, ingredients, allergens, user_profile):
    warnings = []
    if not user_profile:
        return warnings
    allergies  = [a.lower().strip() for a in user_profile.get("allergies", [])]
    conditions = [c.lower().strip() for c in user_profile.get("conditions", [])]
    diet = user_profile.get("diet", "").lower().strip()
    age  = int(user_profile.get("age") or 0)
    sugar  = float(nutriments.get("sugars_100g") or 0)
    salt_g = float(nutriments.get("salt_100g") or 0)
    ing_text = " ".join(i.lower() for i in ingredients)

    for al in allergens:
        for ua in allergies:
            if ua in al["allergen"].lower() or al["allergen"].lower() in ua:
                warnings.append({"type": "red",
                    "title": f"⚠ Contains {al['allergen']} — Matches Your Allergy",
                    "description": f"'{al['found_in']}' matches your declared {ua} allergy. Avoid consumption."})

    for cond in conditions:
        if "diabet" in cond:
            if sugar > 15:
                warnings.append({"type": "red", "title": "Not Recommended for Diabetes",
                    "description": f"Contains {sugar:.1f}g sugar/100g. Can cause blood glucose spikes."})
            elif sugar > 5:
                warnings.append({"type": "orange", "title": "Moderate Sugar — Monitor Intake",
                    "description": f"Contains {sugar:.1f}g sugar/100g. Monitor portion size carefully."})
        if "hypertension" in cond or "blood pressure" in cond:
            if salt_g > 1.5:
                warnings.append({"type": "red", "title": "High Sodium — Hypertension Risk",
                    "description": f"Contains {salt_g:.1f}g salt/100g. Elevated sodium raises blood pressure."})
            elif salt_g > 0.5:
                warnings.append({"type": "orange", "title": "Moderate Sodium",
                    "description": f"Contains {salt_g:.1f}g salt/100g. Consider lower sodium options."})
        if "kidney" in cond and salt_g > 0.3:
            warnings.append({"type": "orange", "title": "Kidney Health Consideration",
                "description": f"Sodium ({salt_g:.1f}g/100g) may be high for kidney disease. Consult your doctor."})
        if "pregnan" in cond:
            if any(kw in ing_text for kw in ARTIFICIAL_COLOUR_KW):
                warnings.append({"type": "orange", "title": "Artificial Colours — Pregnancy Caution",
                    "description": "Contains artificial dyes. Consult your healthcare provider during pregnancy."})
            if any(kw in ing_text for kw in ["caffeine", "coffee", "guarana"]):
                warnings.append({"type": "orange", "title": "May Contain Caffeine",
                    "description": "Limit caffeine intake during pregnancy."})
        if "child" in cond:
            if any(kw in ing_text for kw in ARTIFICIAL_COLOUR_KW):
                warnings.append({"type": "orange", "title": "Artificial Colours — Children Caution",
                    "description": "Linked to hyperactivity in children (EU requires warning label)."})

    non_veg = ["gelatin","gelatine","lard","tallow","cochineal","carmine","rennet"]
    animal  = non_veg + ["milk","whey","casein","lactose","honey","egg","albumin"]
    if diet == "vegetarian":
        for kw in non_veg:
            if kw in ing_text:
                warnings.append({"type": "red", "title": "Not Suitable for Vegetarians",
                    "description": f"Contains '{kw}' — an animal-derived ingredient."}); break
    if diet == "vegan":
        for kw in animal:
            if kw in ing_text:
                warnings.append({"type": "red", "title": "Not Suitable for Vegans",
                    "description": f"Contains '{kw}' — an animal-derived ingredient."}); break
    if age and age < 12 and any(kw in ing_text for kw in ARTIFICIAL_COLOUR_KW):
        warnings.append({"type": "orange", "title": "Artificial Colours — Not Ideal for Children",
            "description": "Some artificial dyes may affect attention levels in children."})
    return warnings

# ── Step 8: Regulatory status ─────────────────────────────
COUNTRY_MAP = [
    ("🇮🇳 FSSAI", "fssai"), ("🇺🇸 FDA", "fda"), ("🇪🇺 EFSA", "efsa"),
    ("🇬🇧 UK", "uk"), ("🇨🇦 Canada", "canada"), ("🇦🇺 Australia", "australia"),
    ("🇯🇵 Japan", "japan"), ("🇸🇬 Singapore", "singapore"),
]

def get_regulatory_status(ingredients, regulatory_raw=None):
    """Check regulatory status. Merges static regulations.csv with per-product CSV data."""
    results = []
    combined = dict(REGULATIONS_DATA)

    # Merge CSV's per-ingredient regulatory data if provided
    if regulatory_raw:
        for ing_key, country_map in regulatory_raw.items():
            entry = {f: "Unknown" for _, f in COUNTRY_MAP}
            entry["notes"] = ""
            for country_str, status in country_map.items():
                cl = country_str.lower()
                if "fda" in cl or "usa" in cl:
                    entry["fda"] = status
                elif "efsa" in cl or "european" in cl:
                    entry["efsa"] = status
                elif "united kingdom" in cl or "uk" in cl:
                    entry["uk"] = status
                elif "canada" in cl:
                    entry["canada"] = status
                elif "australia" in cl:
                    entry["australia"] = status
                elif "japan" in cl:
                    entry["japan"] = status
                elif "singapore" in cl:
                    entry["singapore"] = status
                elif "fssai" in cl or "india" in cl:
                    entry["fssai"] = status
            combined[ing_key] = entry

    for ing in ingredients:
        il = ing.strip().lower()
        entry = combined.get(il)
        if not entry:
            for key, val in combined.items():
                if key in il or il in key:
                    entry = val
                    break
        if not entry:
            continue
        statuses = [{"country": label, "status": entry.get(field, "Unknown")}
                    for label, field in COUNTRY_MAP]
        has_concern = any(s["status"] not in ("Allowed", "Unknown") for s in statuses)
        if has_concern:
            results.append({"ingredient": ing, "regulatory_status": statuses,
                             "notes": entry.get("notes", "")})
    return results

# ── Step 9: News/recalls ──────────────────────────────────
def fetch_recall_news(product_name, brand_name="", ingredients=None, category=None):
    logger.info(f"[News] Fetching for: {product_name}")
    try:
        return get_safety_news(product_name, brand_name, max_articles=6, 
                               ingredients=ingredients, category=category)
    except Exception as e:
        logger.warning(f"[News] Error: {e}")
        return []

# ── Step 10: Related Products ─────────────────────────────
def find_related_products(product, limit=4):
    """Find products in the same category for comparison."""
    if not product:
        return []
    
    categories = product.get("categories", "")
    if not categories:
        return []
    
    # Extract first category for search
    first_category = categories.split(",")[0].strip() if "," in categories else categories
    
    try:
        from utils.product_lookup import CSV_DF
        if CSV_DF.empty:
            return []
        
        # Find products in the same category
        products = []
        for _, row in CSV_DF.iterrows():
            if len(products) >= limit:
                break
            row_cat = str(row.get("category", "")).lower()
            if first_category.lower() in row_cat or row_cat in first_category.lower():
                barcode = str(row.get("barcode_india", "")).strip()
                if barcode and barcode != "nan":
                    # Calculate health score based on ingredients
                    sugar_score = 0
                    for i in range(1, 11):
                        ing = str(row.get(f"india_ingredient_{i}", "")).lower()
                        if "sugar" in ing or "syrup" in ing:
                            sugar_score += 5
                    
                    products.append({
                        "name": str(row.get("product_name", "Unknown")).strip(),
                        "brand": str(row.get("brand", "Unknown")).strip(),
                        "barcode": barcode,
                        "health_score": max(30, 100 - sugar_score)
                    })
        return products
    except Exception as e:
        logger.warning(f"[Related] Error finding related products: {e}")
        return []

# ── Step 11: Better Alternatives ───────────────────────────
def find_better_alternatives(product, current_score, limit=3):
    """Find healthier alternatives using the dataset."""
    if not product:
        return []
    
    alternatives = []
    
    try:
        from utils.product_lookup import CSV_DF
        if CSV_DF.empty:
            return []
        
        nutrition = product.get("nutriments", {})
        current_sugar = float(nutrition.get("sugars_100g", 0) or 0)
        
        # Find better alternatives
        for _, row in CSV_DF.iterrows():
            if len(alternatives) >= limit:
                break
            
            # Skip if same product
            if str(row.get("product_name", "")).lower() == product.get("name", "").lower():
                continue
            
            # Calculate sugar from ingredients
            sugar = 0
            for i in range(1, 11):
                ing = str(row.get(f"india_ingredient_{i}", "")).lower()
                if "sugar" in ing or "syrup" in ing or "dextrose" in ing:
                    sugar += 5
            
            # Prefer products with lower sugar
            if sugar < current_sugar or current_sugar > 5:
                alternatives.append({
                    "name": str(row.get("product_name", "")).strip(),
                    "brand": str(row.get("brand", "")).strip(),
                    "barcode": str(row.get("barcode_india", "")).strip(),
                    "health_score": max(70, 100 - sugar * 10) if sugar < current_sugar else 85,
                    "why_better": f"Lower sugar content ({max(0, sugar)}g vs {current_sugar}g)" if sugar < current_sugar else "Reduced artificial additives"
                })
        
        return alternatives
    except Exception as e:
        logger.warning(f"[Alternatives] Error finding alternatives: {e}")
        return []

# ── Step 12: Scientific References ─────────────────────────
def get_scientific_references(product, ingredients):
    """Get scientific references for ingredients."""
    refs = []
    if not ingredients:
        return refs
    
    for ing in ingredients[:5]:  # Limit to top 5
        ing_lower = ing.lower()
        for key, val in INGREDIENT_KNOWLEDGE.items():
            if key in ing_lower or ing_lower in key:
                if val.get("health_notes"):
                    refs.append({
                        "title": f"Health Information: {ing}",
                        "link": f"https://en.wikipedia.org/wiki/{ing.replace(' ', '_')}"
                    })
                    break
    
    refs.append({
        "title": "FSSAI Food Safety Regulations",
        "link": "https://www.fssai.gov.in"
    })
    
    refs.append({
        "title": "WHO Nutrition Guidelines",
        "link": "https://www.who.int/health-topics/nutrition"
    })
    
    refs.append({
        "title": "EFSA Food Additive Database",
        "link": "https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2023.8750"
    })
    
    return refs[:8]

# ── Step 13: NOVA ─────────────────────────────────────────
NOVA_MAP = {
    1: {"level": 1, "name": "Unprocessed / Minimally Processed",
        "description": "Natural foods altered only by simple processes like cleaning or freezing."},
    2: {"level": 2, "name": "Processed Culinary Ingredients",
        "description": "Substances from nature like oils, butter, sugar, or salt."},
    3: {"level": 3, "name": "Processed Foods",
        "description": "Products made by adding salt, oil, or sugar to whole foods."},
    4: {"level": 4, "name": "Ultra-Processed Foods",
        "description": "Industrial formulations with additives, preservatives, artificial colours, and flavors."}
}

def get_nova_level(nova_group):
    try:
        return NOVA_MAP.get(int(nova_group), {"level": "Unknown", "name": "Not Classified", "description": "NOVA data not available."})
    except (ValueError, TypeError):
        return {"level": "Unknown", "name": "Not Classified", "description": "NOVA data not available."}

# ── Step 14: AI summary ───────────────────────────────────
def generate_ai_summary(product, nutrition, concern_score, allergens, personalized_warnings):
    try:
        from config import get_api_key
        api_key = get_api_key("gemini")
        if api_key and "your_gemini" not in api_key and "placeholder" not in api_key.lower():
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)

            allergen_list = ", ".join(a["allergen"] for a in allergens) or "none"
            factors_list  = " | ".join(concern_score.get("factors", [])) or "none"
            prompt = (
                f"Write a 3-4 sentence consumer-friendly food safety summary using ONLY this data. "
                f"Do NOT invent facts. Plain English, no markdown.\n\n"
                f"Product: {product.get('name')} by {product.get('brand')}\n"
                f"Concern Score: {concern_score.get('score')}/100 ({concern_score.get('level')})\n"
                f"Key Factors: {factors_list}\n"
                f"Allergens: {allergen_list}\n"
                f"Sugar: {nutrition.get('sugars_100g','N/A')}g | Salt: {nutrition.get('salt_100g','N/A')}g | "
                f"Sat Fat: {nutrition.get('saturated-fat_100g','N/A')}g | Fiber: {nutrition.get('fiber_100g','N/A')}g per 100g"
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text.strip()
    except Exception as e:
        logger.warning(f"[AI] Gemini failed: {e}")

    # Rule-based fallback
    name   = product.get("name", "This product")
    brand  = product.get("brand", "")
    score  = concern_score.get("score", 50)
    level  = concern_score.get("level", "")
    factors = concern_score.get("factors", [])
    prefix = name + (f" by {brand}" if brand and brand != "Unknown Brand" else "")
    parts  = [f"{prefix} has a concern score of {score}/100 ({level})."]
    if factors:
        parts.append("Key concerns: " + "; ".join(factors[:3]) + ".")
    if allergens:
        parts.append("Allergens detected: " + ", ".join(a["allergen"] for a in allergens) + ".")
    sugar  = float(nutrition.get("sugars_100g") or 0)
    salt_g = float(nutrition.get("salt_100g") or 0)
    fiber  = float(nutrition.get("fiber_100g") or 0)
    if sugar > 15: parts.append(f"Sugar is high ({sugar:.1f}g/100g) — people with diabetes should limit intake.")
    if salt_g > 1.5: parts.append(f"Sodium is elevated ({salt_g:.1f}g salt/100g) — caution for those with hypertension.")
    if fiber > 3:  parts.append(f"Good source of dietary fiber ({fiber:.1f}g/100g).")
    parts.append("Always read the full label and consult a healthcare professional for personalised advice.")
    return " ".join(parts)

# ── Main pipeline ─────────────────────────────────────────
def analyze_product(barcode, user_profile=None):
    logger.info(f"=== Analysis START barcode={barcode} ===")
    if user_profile is None:
        user_profile = {}

    result = {
        "barcode": barcode, "product": None, "nutrition": {}, "ingredients": [],
        "ingredient_explanations": [], "ingredient_metadata": [],
        "concern_score": None, "allergens": [], "alerts": [],
        "personalized_warnings": [], "regulatory": [], "recalls": [], "news": [],
        "nova": None, "ai_summary": "", "health_score": None, "error": None,
        "dataset_regulatory_report": None
    }

    product = fetch_product_data(barcode)
    if not product:
        result["error"] = f"Product '{barcode}' not found in OpenFoodFacts, USDA, or local dataset."
        return result

    result["product"] = {
        "name":       product.get("name", "Unknown Product"),
        "brand":      product.get("brand", "Unknown Brand"),
        "image_url":  product.get("image_url", ""),
        "categories": product.get("categories", []),
        "nutriscore": product.get("nutriscore_grade", ""),
        "nova_group": product.get("nova_group"),
        "source":     product.get("source", "OpenFoodFacts"),
        "manufacturer": product.get("manufacturer", ""),
        "origin":     product.get("origin", ""),
        # CSV-enriched fields
        "health_note":      product.get("health_note", ""),
        "health_concern":   product.get("health_concern", ""),
        "consumer_note":    product.get("consumer_note", ""),
        "key_differences":  product.get("key_differences", ""),
    }

    nutrition  = product.get("nutriments", {})
    result["nutrition"] = nutrition

    # ── Build the UNIFIED ingredient list ─────────────────────────
    merged_records = merge_ingredients_and_additives(product)
    ingredients    = [r["ingredient_name"] for r in merged_records]

    result["ingredients"]         = ingredients
    result["ingredient_metadata"] = merged_records

    logger.info(
        f"[Pipeline] {len(ingredients)} ingredients after merge "
        f"(text={len(parse_ingredients(product.get('ingredients_text','')))} "
        f"+ additives_tags={len(product.get('additives_tags') or [])} "
        f"+ ingredients_tags={len(product.get('ingredients_tags') or [])})"
    )

    risks = check_banned_ingredients(ingredients, BANNED_DF)
    logger.info(f"[Pipeline] {len(risks)} risks flagged")

    result["ingredient_explanations"] = lookup_ingredient_explanations(ingredients, merged_records)
    result["concern_score"] = compute_concern_score(nutrition, ingredients, risks, user_profile)
    logger.info(f"[Pipeline] Score={result['concern_score']['score']} Level={result['concern_score']['level']}")

    allergens = detect_allergens(ingredients)
    result["allergens"] = allergens
    result["alerts"]    = [a["allergen"] for a in allergens]
    logger.info(f"[Pipeline] {len(allergens)} allergens")

    result["personalized_warnings"] = generate_personalized_warnings(nutrition, ingredients, allergens, user_profile)
    result["regulatory"] = get_regulatory_status(ingredients, product.get("regulatory_raw", {}))
    logger.info(f"[Pipeline] {len(result['regulatory'])} regulatory concerns")

    try:
        from utils.excel_parser import get_additives_report
        result["additive_regulatory_report"] = get_additives_report(ingredients)
        logger.info(f"[Pipeline] Loaded {len(result['additive_regulatory_report'])} additives from Excel report")
    except Exception as e:
        logger.error(f"[Pipeline] Error running Excel additive report: {e}")
        result["additive_regulatory_report"] = []

    # Enhanced news fetch with ingredients and category
    result["news"] = fetch_recall_news(
        product.get("name", ""),
        brand_name=product.get("brand", ""),
        ingredients=ingredients,
        category=product.get("categories", "")
    )
    
    result["nova"]         = get_nova_level(product.get("nova_group"))
    result["health_score"] = calculate_health_score(nutrition)
    result["ai_summary"]   = generate_ai_summary(
        result["product"], nutrition, result["concern_score"], allergens, result["personalized_warnings"]
    )

    # Related products
    result["related_products"] = find_related_products(product)
    
    # Better alternatives
    result["better_alternatives"] = find_better_alternatives(product, result["concern_score"]["score"])
    
    # Scientific references
    result["scientific_references"] = get_scientific_references(product, ingredients)

    # Dataset Regulatory Check
    try:
        result["dataset_regulatory_report"] = check_ingredients_against_dataset(ingredients)
        ds = result["dataset_regulatory_report"]["summary"]
        logger.info(
            f"[Pipeline] Dataset check — Banned:{ds['banned']} "
            f"Restricted:{ds['restricted']} Allowed:{ds['allowed']} NoMatch:{ds['no_match']}"
        )
    except Exception as exc:
        logger.warning(f"[Pipeline] Dataset regulatory check failed: {exc}")
        result["dataset_regulatory_report"] = None

    logger.info(f"=== Analysis DONE: {product.get('name')} ===")
    return result