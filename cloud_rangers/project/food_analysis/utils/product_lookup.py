import openfoodfacts
import requests
import streamlit as st
from .usda_client import USDAClient, normalize_usda_data

def lookup_product(barcode):
    """
    Fetches product data from OpenFoodFacts.
    Returns a dictionary of product data or None if not found.
    """
    try:
        api = openfoodfacts.API(user_agent="FoodAnalysisApp/1.0")
        code, result = api.product.get(barcode)

        if result['status'] == 1:
            product = result['product']
            return {
                'name': product.get('product_name', 'Unknown Product'),
                'brand': product.get('brands', 'Unknown Brand'),
                'ingredients_text': product.get('ingredients_text', ''),
                'image_url': product.get('image_url', ''),
                'nutriments': product.get('nutriments', {}),
                'categories': product.get('categories', ''),
                'nova_group': product.get('nova_group', None),
                'nutriscore_grade': product.get('nutriscore_grade', None),
                'source': 'OpenFoodFacts'
            }
        else:
            # Fallback to USDA or other APIs could go here
            # For now, return None to indicate failure
            print(f"Product not found in OpenFoodFacts: {barcode}. Result: {result}")
            return None

    except Exception as e:
        print(f"Error looking up product in OpenFoodFacts: {e}")
        # Proceed to fallback even if exception

    # Fallback to USDA
    try:
        usda = USDAClient()
        # If barcode is numeric, we can try searching it as a GTPIN or similar in USDA
        # But USDA search is text based usually. Detailed lookup requires FDC ID.
        # "search" endpoint accepts "query". We can pass the barcode.
        print(f"Searching USDA for barcode: {barcode}")
        results = usda.search_foods(barcode)
        
        if results:
            # Take the first result
            item = results[0]
            # Need to get details for nutrients
            fdc_id = item.get("fdcId")
            if fdc_id:
                details = usda.get_food_details(fdc_id)
                return normalize_usda_data(details)
                
    except Exception as e:
        print(f"Error looking up product in USDA: {e}")

    return None
