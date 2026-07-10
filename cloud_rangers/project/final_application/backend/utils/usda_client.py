import requests
import sys
import os
try:
    from ..config import get_api_key
except ImportError:
    # Fallback to direct import if backend is in path
    try:
        from config import get_api_key
    except ImportError:
        # If running from root and backend not in path, add it
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import get_api_key

class USDAClient:
    def __init__(self):
        self.api_key = get_api_key("usda")
        self.base_url = "https://api.nal.usda.gov/fdc/v1"

    def search_foods(self, query, page_size=5):
        """
        Search for foods by text query.
        """
        url = f"{self.base_url}/foods/search"
        params = {
            "api_key": self.api_key,
            "query": query,
            "pageSize": page_size,
            "dataType": ["Branded", "Foundation"]
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json().get('foods', [])
        except Exception as e:
            print(f"USDA Search Error: {e}")
            return []

    def get_food_details(self, fdc_id):
        """
        Get detailed info for a specific food by FDC ID.
        """
        url = f"{self.base_url}/food/{fdc_id}"
        params = {"api_key": self.api_key}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"USDA Details Error: {e}")
            return None

def normalize_usda_data(usda_data):
    """
    Convert USDA data format to our internal product format.
    """
    if not usda_data:
        return None

    # Brands allow us to be specific, otherwise it's a generic food
    brand = usda_data.get("brandOwner", "Generic / Unknown")
    description = usda_data.get("description", "Unknown Product")
    
    # Ingredients
    ingredients = usda_data.get("ingredients", "")
    
    # Nutrients - USDA extraction is tricky, they use nutrientNumbers or names
    nutrients = {}
    for nutrient in usda_data.get("foodNutrients", []):
        name = nutrient.get("nutrientName", "").lower()
        amount = nutrient.get("value", 0)
        
        if "sugar" in name:
            nutrients["sugars_100g"] = amount
        elif "fiber" in name:
            nutrients["fiber_100g"] = amount
        elif "protein" in name:
            nutrients["proteins_100g"] = amount
        elif "fat" in name and "saturated" in name:
            nutrients["saturated-fat_100g"] = amount
        elif "sodium" in name:
             # USDA usually gives mg, OpenFoodFacts uses g for salt. 
             # 1g salt approx 0.4g sodium? Or direct conversion?
             # Let's keep it simple: just track sodium for now or convert loosely.
             # score engine expecting salt_100g. Salt = Sodium * 2.5
             nutrients["salt_100g"] = (amount / 1000) * 2.5 

    return {
        "name": description,
        "brand": brand,
        "ingredients_text": ingredients,
        "image_url": "", # USDA doesn't usually provide standard product images
        "nutriments": nutrients,
        "categories": [usda_data.get("foodCategory", "")],
        "nova_group": None,
        "nutriscore_grade": None,
        "source": "USDA"
    }
