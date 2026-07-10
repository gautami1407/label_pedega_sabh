import sys
import os

# Add the project directory to python path
sys.path.append(os.path.abspath("cloud_rangers/project/food_analysis"))

from utils.product_lookup import lookup_product
from utils.data_processor import normalize_product_data, parse_ingredients
from utils.risk_engine import load_banned_ingredients, check_banned_ingredients, calculate_health_score

def test_pipeline():
    with open("verification_log.txt", "w", encoding="utf-8") as log:
        def log_print(msg):
            print(msg)
            log.write(msg + "\n")

        log_print("Starting pipeline verification...")
        
        # 1. Mock Barcode (Coca-Cola 330ml)
        barcode = "5449000000996" 
        log_print(f"Testing with barcode: {barcode}")

        # 2. Product Lookup
        log_print("Looking up product...")
        raw_data = lookup_product(barcode)
        
        if not raw_data:
            log_print("❌ Product lookup failed! Using MOCK DATA for rest of pipeline.")
            # Mock Data for testing downstream logic
            raw_data = {
                'code': barcode,
                'status': 1,
                'product': {
                    'product_name': 'Mock Coca-Cola',
                    'brands': 'Coca-Cola',
                    'ingredients_text': 'Carbonated Water, Sugar, Color (Caramel E150d), Phosphoric Acid, Natural Flavorings, Caffeine.',
                    'image_url': 'http://example.com/coke.jpg',
                    'nutriments': {'sugars_100g': 10.6, 'salt_100g': 0},
                    'categories': 'Beverages,Carbonated drinks,Sodas',
                    'nova_group': 4,
                    'nutriscore_grade': 'e'
                }
            }
            # Extract inner product dict as lookup_product already extracts it if successful?
            # Wait, lookup_product returns the extracted dict if success, or None if fail.
            # So I should mimic the structure returned by lookup_product
            raw_data = {
                'name': 'Mock Coca-Cola',
                'brand': 'Coca-Cola',
                'ingredients_text': 'Carbonated Water, Sugar, Color (Caramel E150d), Phosphoric Acid, Natural Flavorings, Caffeine.',
                'image_url': 'http://example.com/coke.jpg',
                'nutriments': {'sugars_100g': 10.6, 'salt_100g': 0},
                'categories': 'Beverages,Carbonated drinks,Sodas',
                'nova_group': 4,
                'nutriscore_grade': 'e',
                'source': 'Mock'
            }
        
        print(f"✅ Product found/mocked: {raw_data.get('name', 'Unknown')}")

        # 3. Data Normalization
        log_print("Normalizing data...")
        product = normalize_product_data(raw_data)
        log_print(f"✅ Data normalized. Ingredients text length: {len(product['ingredients_text'])}")

        # 4. Ingredient Parsing
        log_print("Parsing ingredients...")
        ingredients = parse_ingredients(product['ingredients_text'])
        log_print(f"✅ Parsed {len(ingredients)} ingredients: {ingredients[:3]}...")

        # 5. Risk Check
        log_print("Checking risks...")
        banned_df = load_banned_ingredients("cloud_rangers/project/food_analysis/data/banned_ingredients.csv")
        if banned_df.empty:
            log_print("❌ Failed to load banned ingredients CSV!")
        else:
            risks = check_banned_ingredients(ingredients, banned_df)
            log_print(f"✅ Risk check complete. Found {len(risks)} risks.")
            for risk in risks:
                log_print(f"   - Warning: {risk['found_as']} -> {risk['ingredient']} ({risk['risk_level']})")

        # 6. Health Score
        log_print("Calculating health score...")
        score = calculate_health_score(product['nutriments'])
        log_print(f"✅ Health Score: {score}")

        # 7. Test High Risk Scenario
        log_print("\n--- Testing High Risk Scenario ---")
        risky_ingredients = ["water", "red 40", "sugar", "brominated vegetable oil"]
        log_print(f"Testing ingredients: {risky_ingredients}")
        risks = check_banned_ingredients(risky_ingredients, banned_df)
        log_print(f"Found {len(risks)} risks.")
        for risk in risks:
            log_print(f"   - Warning: {risk['found_as']} -> {risk['ingredient']} ({risk['risk_level']})")

        log_print("\nVerification complete.")

if __name__ == "__main__":
    test_pipeline()
