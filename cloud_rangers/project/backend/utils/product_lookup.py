"""
Product Lookup — Multi-source pipeline
1. Local fallback (known products)
2. OpenFoodFacts API (full field extraction)
3. Local CSV dataset
4. USDA FoodData Central
"""
import os
import logging
import pandas as pd
import requests
from .usda_client import USDAClient, normalize_usda_data

logger = logging.getLogger(__name__)

DATASET_PATH = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "dataset", "combine_enriched.csv"
))

def load_local_dataset():
    if not os.path.exists(DATASET_PATH):
        return []
    try:
        df = pd.read_csv(DATASET_PATH)
        return df.to_dict("records")
    except Exception as exc:
        logger.warning(f"Could not load local dataset: {exc}")
        return []

LOCAL_DATASET = load_local_dataset()

FALLBACK_PRODUCTS = {
    "8901030895489": {
        "name": "Maggi Masala Noodles", "brand": "Nestle",
        "ingredients_text": "wheat flour, refined palm oil, salt, spices, flavour enhancer (monosodium glutamate), onion powder, turmeric",
        "image_url": "https://images.openfoodfacts.org/images/products/890/103/089/5489/front_en.44.400.jpg",
        "nutriments": {"energy-kcal_100g": 450, "fat_100g": 18, "saturated-fat_100g": 8,
                       "sugars_100g": 2, "salt_100g": 1.8, "proteins_100g": 8, "fiber_100g": 2,
                       "carbohydrates_100g": 65},
        "categories": "Instant noodles, Processed foods", "nova_group": "4", "nutriscore_grade": "d",
        "allergens_tags": ["en:gluten"], "additives_tags": ["en:e621"],
        "source": "Local fallback"
    },
    "8901063076665": {
        "name": "Parle-G Biscuit", "brand": "Parle",
        "ingredients_text": "wheat flour, sugar, edible vegetable oil, invert syrup, leavening agents, salt, milk solids, dextrose",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 440, "fat_100g": 15, "saturated-fat_100g": 5,
                       "sugars_100g": 20, "salt_100g": 0.9, "proteins_100g": 6, "fiber_100g": 2,
                       "carbohydrates_100g": 68},
        "categories": "Biscuits, Snacks", "nova_group": "4", "nutriscore_grade": "c",
        "allergens_tags": ["en:gluten", "en:milk"],
        "source": "Local fallback"
    },
    "0049000006346": {
        "name": "Coca-Cola Classic", "brand": "The Coca-Cola Company",
        "ingredients_text": "carbonated water, sugar, colour (caramel e150d), phosphoric acid, natural flavourings including caffeine",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 42, "fat_100g": 0, "saturated-fat_100g": 0,
                       "sugars_100g": 10.6, "salt_100g": 0.0, "proteins_100g": 0.0, "fiber_100g": 0,
                       "carbohydrates_100g": 10.6},
        "categories": "Beverages, Carbonated drinks", "nova_group": "4", "nutriscore_grade": "e",
        "source": "Local fallback"
    },
    "7622210449283": {
        "name": "KitKat 4 Finger", "brand": "Nestle",
        "ingredients_text": "sugar, wheat flour, cocoa butter, skimmed milk powder, cocoa mass, palm oil, lactose, milk fat, soy lecithin, polyglycerol polyricinoleate, vanillin, caramel e150a",
        "image_url": "",
        "nutriments": {"energy-kcal_100g": 518, "fat_100g": 27, "saturated-fat_100g": 14.8,
                       "sugars_100g": 51.8, "salt_100g": 0.13, "proteins_100g": 7.3, "fiber_100g": 1.5,
                       "carbohydrates_100g": 59},
        "categories": "Chocolate bars, Confectionery", "nova_group": "4", "nutriscore_grade": "e",
        "allergens_tags": ["en:gluten", "en:milk", "en:soybeans"],
        "source": "Local fallback"
    }
}


def lookup_product(barcode):
    """
    Multi-source product lookup.
    Priority: local fallback -> OpenFoodFacts -> local CSV -> USDA
    """
    # 1. Local fallback
    if barcode in FALLBACK_PRODUCTS:
        logger.info(f"[Lookup] Local fallback hit: {barcode}")
        return FALLBACK_PRODUCTS[barcode]

    # 2. OpenFoodFacts
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url, timeout=12, headers={"User-Agent": "LabelPadegha/2.0"})
        response.raise_for_status()
        result = response.json()

        if result.get('status') == 1 and result.get('product'):
            p = result['product']
            name = (p.get('product_name_en') or p.get('product_name_hi') or
                    p.get('product_name') or 'Unknown Product')
            image_url = (p.get('image_front_url') or p.get('image_url') or
                         p.get('image_front_small_url') or '')
            nutriments = p.get('nutriments', {})
            # Normalise energy to kcal key if missing
            if 'energy-kcal_100g' not in nutriments and 'energy_100g' in nutriments:
                nutriments['energy-kcal_100g'] = round(float(nutriments['energy_100g']) / 4.184, 1)
            allergen_tags = p.get('allergens_tags', [])
            allergens_clean = [t.replace('en:', '').replace('-', ' ').title() for t in allergen_tags]
            logger.info(f"[Lookup] OFF found: {name} (nova={p.get('nova_group')}, score={p.get('nutriscore_grade')})")
            return {
                'name':             name,
                'brand':            p.get('brands', 'Unknown Brand'),
                'ingredients_text': p.get('ingredients_text', ''),
                'image_url':        image_url,
                'nutriments':       nutriments,
                'categories':       p.get('categories', ''),
                'nova_group':       p.get('nova_group'),
                'nutriscore_grade': p.get('nutriscore_grade'),
                'allergens':        allergens_clean,
                'additives':        p.get('additives_tags', []),
                'countries':        p.get('countries', ''),
                'labels':           p.get('labels', ''),
                'packaging':        p.get('packaging', ''),
                'source':           'OpenFoodFacts'
            }
        logger.warning(f"[Lookup] OFF: not found for {barcode}")
    except Exception as e:
        logger.warning(f"[Lookup] OFF error: {e}")

    # 3. Local CSV dataset
    for row in LOCAL_DATASET:
        if str(row.get("id") or "").strip() == str(barcode).strip():
            logger.info(f"[Lookup] Local CSV hit: {barcode}")
            return {
                "name":             row.get("product_name") or "Unknown Product",
                "brand":            row.get("brand") or "Unknown Brand",
                "ingredients_text": row.get("india_ingredient_1") or row.get("ingredient_explanation") or "",
                "image_url":        "",
                "nutriments":       {},
                "categories":       row.get("category") or "",
                "nova_group":       None,
                "nutriscore_grade": None,
                "source":           "Local dataset"
            }

    # 4. USDA fallback
    try:
        usda = USDAClient()
        logger.info(f"[Lookup] Trying USDA for: {barcode}")
        results = usda.search_foods(barcode)
        if results:
            fdc_id = results[0].get("fdcId")
            if fdc_id:
                details = usda.get_food_details(fdc_id)
                normalized = normalize_usda_data(details)
                if normalized:
                    logger.info(f"[Lookup] USDA found: {normalized.get('name')}")
                    return normalized
    except Exception as e:
        logger.warning(f"[Lookup] USDA error: {e}")

    logger.warning(f"[Lookup] All sources exhausted for barcode: {barcode}")
    return None
