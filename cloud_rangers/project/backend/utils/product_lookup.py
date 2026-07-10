"""
Product Lookup Pipeline
========================
Priority:
  1. CSV barcode_india  — exact barcode match (Maggi 8901058851311, Pringles, Cadbury)
  2. OpenFoodFacts API  — live barcode lookup for everything else
  3. CSV name match     — enrich OFF result with health_note / regulatory from CSV
  4. Hardcoded fallback — key Indian products with full nutrition data
  5. USDA              — last resort text search
"""
import os
import logging
import pandas as pd
import requests
from .usda_client import USDAClient, normalize_usda_data

logger = logging.getLogger(__name__)

# ── Dataset path ──────────────────────────────────────────
DATASET_PATH = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "dataset", "combine_enriched.csv"
))

# ── Load CSV once ─────────────────────────────────────────
def _load_csv():
    if not os.path.exists(DATASET_PATH):
        logger.warning(f"[CSV] Not found: {DATASET_PATH}")
        return pd.DataFrame()
    try:
        df = pd.read_csv(DATASET_PATH, dtype=str).fillna("")
        logger.info(f"[CSV] Loaded {len(df)} rows from combine_enriched.csv")
        return df
    except Exception as e:
        logger.error(f"[CSV] Load error: {e}")
        return pd.DataFrame()

CSV_DF = _load_csv()

# ── Parse global_regulation column into structured dict ───
def _parse_regulatory(row):
    raw = str(row.get("global_regulation", ""))
    if not raw:
        return {}
    result = {}
    for block in raw.split(" | "):
        if ":" not in block:
            continue
        ing_part, countries_part = block.split(":", 1)
        ing_key = ing_part.strip().lower()
        country_statuses = {}
        for cs in countries_part.split(";"):
            cs = cs.strip()
            if "=" in cs:
                country, status = cs.split("=", 1)
                country_statuses[country.strip()] = status.strip()
        if ing_key:
            result[ing_key] = country_statuses
    return result

# ── Build product dict from a CSV row ─────────────────────
def _row_to_product(row, source_tag="CSV"):
    india_ings = []
    for i in range(1, 11):
        val = str(row.get(f"india_ingredient_{i}", "")).strip()
        if val:
            india_ings.append(val)
    ingredients_text = ", ".join(india_ings)

    allergens_raw = str(row.get("allergens", "")).strip()
    allergens = [a.strip() for a in allergens_raw.split(",") if a.strip()]

    additives_raw = str(row.get("notable_additives", "")).strip()
    additives = [a.strip() for a in additives_raw.split(",") if a.strip()]

    return {
        "name":             str(row.get("product_name", "Unknown Product")).strip(),
        "brand":            str(row.get("brand", "Unknown Brand")).strip(),
        "image_url":        "",
        "ingredients_text": ingredients_text,
        "nutriments":       {},   # CSV has no nutrition data
        "categories":       str(row.get("category", "")).strip(),
        "nova_group":       None,
        "nutriscore_grade": None,
        "allergens":        allergens,
        "additives":        additives,
        "health_note":      str(row.get("health_note", "")).strip(),
        "health_concern":   str(row.get("health_concern", "")).strip(),
        "consumer_note":    str(row.get("consumer_note", "")).strip(),
        "key_differences":  str(row.get("key_differences", "")).strip(),
        "regulatory_raw":   _parse_regulatory(row),
        "source":           f"CSV ({source_tag})",
    }

# ── CSV lookup by barcode ─────────────────────────────────
def _csv_by_barcode(barcode):
    if CSV_DF.empty:
        return None
    bc = str(barcode).strip()
    mask = CSV_DF["barcode_india"].str.strip() == bc
    if mask.any():
        row = CSV_DF[mask].iloc[0]
        logger.info(f"[CSV] Barcode match: {barcode} -> {row.get('product_name')}")
        return _row_to_product(row, "barcode")
    return None

# ── CSV lookup by product name ────────────────────────────
def _csv_by_name(name, brand=""):
    if CSV_DF.empty or not name:
        return None
    q = name.lower().strip()
    b = brand.lower().strip()

    # Exact name match
    mask = CSV_DF["product_name"].str.lower().str.strip() == q
    if mask.any():
        return _row_to_product(CSV_DF[mask].iloc[0], "name-exact")

    # Name contains query
    mask = CSV_DF["product_name"].str.lower().str.contains(q, regex=False, na=False)
    if mask.any():
        return _row_to_product(CSV_DF[mask].iloc[0], "name-contains")

    # Query contains CSV name
    for _, row in CSV_DF.iterrows():
        pname = str(row.get("product_name", "")).lower().strip()
        if pname and len(pname) > 3 and pname in q:
            return _row_to_product(row, "name-partial")

    # Brand match as fallback
    if b:
        mask = CSV_DF["brand"].str.lower().str.contains(b, regex=False, na=False)
        if mask.any():
            # Only return if name also has some overlap
            for _, row in CSV_DF[mask].iterrows():
                pname = str(row.get("product_name", "")).lower()
                q_words = [w for w in q.split() if len(w) >= 4]
                if any(w in pname for w in q_words):
                    return _row_to_product(row, "brand+name")

    # Word overlap (2+ significant words match)
    q_words = [w for w in q.split() if len(w) >= 4]
    if len(q_words) >= 2:
        best, best_score = None, 0
        for _, row in CSV_DF.iterrows():
            pname = str(row.get("product_name", "")).lower()
            score = sum(1 for w in q_words if w in pname)
            if score > best_score:
                best_score, best = score, row
        if best_score >= 2:
            return _row_to_product(best, "word-overlap")

    return None

# ── OpenFoodFacts lookup ──────────────────────────────────
def _off_by_barcode(barcode):
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        r = requests.get(url, timeout=12,
                         headers={"User-Agent": "LabelPadegha/2.0 (+labelpadegha.com)"})
        r.raise_for_status()
        data = r.json()

        if data.get("status") == 1 and data.get("product"):
            p = data["product"]
            name = (p.get("product_name_en") or p.get("product_name_hi") or
                    p.get("product_name") or "").strip()
            if not name:
                logger.info(f"[OFF] Barcode {barcode} found but no product name")
                return None

            image_url = (p.get("image_front_url") or p.get("image_url") or
                         p.get("image_front_small_url") or "")

            nutriments = dict(p.get("nutriments", {}))
            if "energy-kcal_100g" not in nutriments and "energy_100g" in nutriments:
                try:
                    nutriments["energy-kcal_100g"] = round(
                        float(nutriments["energy_100g"]) / 4.184, 1)
                except Exception:
                    pass

            allergens = [t.replace("en:", "").replace("-", " ").title()
                         for t in p.get("allergens_tags", [])]

            logger.info(f"[OFF] Found: {name} | nova={p.get('nova_group')}")
            return {
                "name":             name,
                "brand":            p.get("brands", "Unknown Brand"),
                "image_url":        image_url,
                "ingredients_text": p.get("ingredients_text", ""),
                "nutriments":       nutriments,
                "categories":       p.get("categories", ""),
                "nova_group":       p.get("nova_group"),
                "nutriscore_grade": p.get("nutriscore_grade"),
                "allergens":        allergens,
                "additives":        p.get("additives_tags", []),
                "countries":        p.get("countries", ""),
                "labels":           p.get("labels", ""),
                "packaging":        p.get("packaging", ""),
                "health_note":      "",
                "health_concern":   "",
                "consumer_note":    "",
                "key_differences":  "",
                "regulatory_raw":   {},
                "source":           "OpenFoodFacts",
            }
        logger.info(f"[OFF] Not found: {barcode}")
    except Exception as e:
        logger.warning(f"[OFF] Error: {e}")
    return None

# ── Hardcoded Indian products (full nutrition, verified) ──
FALLBACK_PRODUCTS = {
    "8901030895489": {
        "name": "Maggi Masala Noodles", "brand": "Nestle",
        "ingredients_text": "wheat flour, refined palm oil, salt, spices, flavour enhancer (monosodium glutamate), onion powder, turmeric",
        "image_url": "https://images.openfoodfacts.org/images/products/890/103/089/5489/front_en.44.400.jpg",
        "nutriments": {"energy-kcal_100g": 450, "fat_100g": 18, "saturated-fat_100g": 8,
                       "sugars_100g": 2, "salt_100g": 1.8, "proteins_100g": 8, "fiber_100g": 2,
                       "carbohydrates_100g": 65},
        "categories": "Instant noodles, Processed foods", "nova_group": "4", "nutriscore_grade": "d",
        "allergens": ["Gluten"], "additives": [], "health_note": "",
        "health_concern": "", "consumer_note": "", "key_differences": "", "regulatory_raw": {},
        "source": "Local fallback"
    },
    "8901058851311": {
        "name": "Maggi 2-Minute Masala Noodles", "brand": "Nestle",
        "ingredients_text": "wheat flour, refined palm oil, salt, spices, flavour enhancer (monosodium glutamate), onion powder, turmeric",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 450, "fat_100g": 18, "saturated-fat_100g": 8,
                       "sugars_100g": 2, "salt_100g": 1.8, "proteins_100g": 8, "fiber_100g": 2,
                       "carbohydrates_100g": 65},
        "categories": "Instant noodles, Processed foods", "nova_group": "4", "nutriscore_grade": "d",
        "allergens": ["Gluten"], "additives": [], "health_note": "", "health_concern": "",
        "consumer_note": "", "key_differences": "", "regulatory_raw": {}, "source": "Local fallback"
    },
    "8901063076665": {
        "name": "Parle-G Biscuit", "brand": "Parle",
        "ingredients_text": "wheat flour, sugar, edible vegetable oil, invert syrup, leavening agents, salt, milk solids, dextrose",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 440, "fat_100g": 15, "saturated-fat_100g": 5,
                       "sugars_100g": 20, "salt_100g": 0.9, "proteins_100g": 6, "fiber_100g": 2,
                       "carbohydrates_100g": 68},
        "categories": "Biscuits, Snacks", "nova_group": "4", "nutriscore_grade": "c",
        "allergens": ["Gluten", "Milk"], "additives": [], "health_note": "",
        "health_concern": "", "consumer_note": "", "key_differences": "", "regulatory_raw": {},
        "source": "Local fallback"
    },
    "0049000006346": {
        "name": "Coca-Cola Classic", "brand": "The Coca-Cola Company",
        "ingredients_text": "carbonated water, sugar, colour (caramel e150d), phosphoric acid, natural flavourings including caffeine",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 42, "sugars_100g": 10.6, "salt_100g": 0.0,
                       "fat_100g": 0, "carbohydrates_100g": 10.6, "proteins_100g": 0},
        "categories": "Beverages, Carbonated drinks", "nova_group": "4", "nutriscore_grade": "e",
        "allergens": [], "additives": [], "health_note": "", "health_concern": "",
        "consumer_note": "", "key_differences": "", "regulatory_raw": {}, "source": "Local fallback"
    },
    "7622210449283": {
        "name": "KitKat 4 Finger", "brand": "Nestle",
        "ingredients_text": "sugar, wheat flour, cocoa butter, skimmed milk powder, cocoa mass, palm oil, lactose, milk fat, soy lecithin, polyglycerol polyricinoleate, vanillin, caramel e150a",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 518, "fat_100g": 27, "saturated-fat_100g": 14.8,
                       "sugars_100g": 51.8, "salt_100g": 0.13, "proteins_100g": 7.3,
                       "fiber_100g": 1.5, "carbohydrates_100g": 59},
        "categories": "Chocolate bars, Confectionery", "nova_group": "4", "nutriscore_grade": "e",
        "allergens": ["Gluten", "Milk", "Soy"], "additives": [], "health_note": "",
        "health_concern": "", "consumer_note": "", "key_differences": "", "regulatory_raw": {},
        "source": "Local fallback"
    },
    "7622201149406": {
        "name": "Cadbury Dairy Milk", "brand": "Cadbury (Mondelez)",
        "ingredients_text": "sugar, cocoa butter, cocoa mass, skimmed milk powder, milk fat, soy lecithin, polyglycerol polyricinoleate, vanillin",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 535, "fat_100g": 30, "saturated-fat_100g": 18,
                       "sugars_100g": 57, "salt_100g": 0.18, "proteins_100g": 8,
                       "fiber_100g": 1, "carbohydrates_100g": 59},
        "categories": "Chocolate, Confectionery", "nova_group": "4", "nutriscore_grade": "e",
        "allergens": ["Milk", "Soy"], "additives": [], "health_note": "",
        "health_concern": "", "consumer_note": "", "key_differences": "", "regulatory_raw": {},
        "source": "Local fallback"
    },
    "8886467122392": {
        "name": "Pringles Original", "brand": "Pringles (Kellanova)",
        "ingredients_text": "dried potatoes, vegetable oil, rice flour, wheat starch, maltodextrin, salt, emulsifier (e471)",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 530, "fat_100g": 33, "saturated-fat_100g": 9,
                       "sugars_100g": 1.5, "salt_100g": 1.1, "proteins_100g": 4,
                       "fiber_100g": 3, "carbohydrates_100g": 55},
        "categories": "Chips, Snacks", "nova_group": "4", "nutriscore_grade": "e",
        "allergens": ["Gluten", "Milk"], "additives": [], "health_note": "",
        "health_concern": "", "consumer_note": "", "key_differences": "", "regulatory_raw": {},
        "source": "Local fallback"
    },
}

# ── Merge CSV enrichment into a product dict ──────────────
def _enrich_with_csv(product, csv_row):
    """Add CSV health/regulatory fields to an OFF/fallback product."""
    if not csv_row:
        return product
    # Only fill if empty
    if not product.get("health_note"):
        product["health_note"] = csv_row.get("health_note", "")
    if not product.get("health_concern"):
        product["health_concern"] = csv_row.get("health_concern", "")
    if not product.get("consumer_note"):
        product["consumer_note"] = csv_row.get("consumer_note", "")
    if not product.get("key_differences"):
        product["key_differences"] = csv_row.get("key_differences", "")
    if not product.get("regulatory_raw"):
        product["regulatory_raw"] = csv_row.get("regulatory_raw", {})
    # Prefer CSV ingredients if OFF returned none
    if not product.get("ingredients_text", "").strip():
        product["ingredients_text"] = csv_row.get("ingredients_text", "")
    if not product.get("allergens"):
        product["allergens"] = csv_row.get("allergens", [])
    product["source"] = product.get("source", "Unknown") + " + CSV"
    return product

# ── Main entry point ──────────────────────────────────────
def lookup_product(barcode: str):
    """
    Lookup a product by barcode. Returns standardised dict or None.
    """
    barcode = str(barcode).strip()
    logger.info(f"[Lookup] barcode={barcode}")

    # 1. CSV barcode_india exact match
    csv_bc = _csv_by_barcode(barcode)
    if csv_bc:
        # Try to get image + nutrition from OFF and merge
        off = _off_by_barcode(barcode)
        if off:
            # Use OFF for image/nutrition, CSV for ingredients/regulatory
            if off.get("image_url"):
                csv_bc["image_url"] = off["image_url"]
            if off.get("nutriments"):
                csv_bc["nutriments"] = off["nutriments"]
            if off.get("nova_group"):
                csv_bc["nova_group"] = off["nova_group"]
            if off.get("nutriscore_grade"):
                csv_bc["nutriscore_grade"] = off["nutriscore_grade"]
            csv_bc["source"] = "CSV + OpenFoodFacts"
        return csv_bc

    # 2. Hardcoded fallback barcode match
    if barcode in FALLBACK_PRODUCTS:
        product = dict(FALLBACK_PRODUCTS[barcode])
        logger.info(f"[Lookup] Hardcoded fallback: {product['name']}")
        # Try to enrich with CSV by name
        csv_match = _csv_by_name(product["name"], product.get("brand", ""))
        if csv_match:
            product = _enrich_with_csv(product, csv_match)
        return product

    # 3. OpenFoodFacts barcode lookup
    off_result = _off_by_barcode(barcode)
    if off_result:
        name  = off_result.get("name", "")
        brand = off_result.get("brand", "")
        # Enrich with CSV data
        csv_match = _csv_by_name(name, brand)
        if csv_match:
            off_result = _enrich_with_csv(off_result, csv_match)
        return off_result

    # 4. USDA last resort
    try:
        usda = USDAClient()
        results = usda.search_foods(barcode, page_size=3)
        if results:
            fdc_id = results[0].get("fdcId")
            if fdc_id:
                details = usda.get_food_details(fdc_id)
                normalized = normalize_usda_data(details)
                if normalized:
                    logger.info(f"[USDA] Found: {normalized.get('name')}")
                    normalized.setdefault("health_note", "")
                    normalized.setdefault("health_concern", "")
                    normalized.setdefault("consumer_note", "")
                    normalized.setdefault("key_differences", "")
                    normalized.setdefault("regulatory_raw", {})
                    return normalized
    except Exception as e:
        logger.warning(f"[USDA] Error: {e}")

    logger.warning(f"[Lookup] All sources exhausted for: {barcode}")
    return None
