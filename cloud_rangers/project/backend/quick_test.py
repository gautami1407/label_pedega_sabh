"""Quick integration test for product lookup pipeline."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.product_lookup import lookup_product
from utils.data_processor import normalize_product_data, parse_ingredients, merge_ingredients_and_additives
from utils.risk_engine import load_banned_ingredients, check_banned_ingredients
from utils.analysis_engine import analyze_product

# Test 1: Product lookup
print("=" * 60)
print("TEST 1: Product Lookup (Maggi - fallback barcode)")
print("=" * 60)
product = lookup_product("8901030895489")
if product:
    print(f"[OK] Found: {product.get('name')} (source: {product.get('source')})")
else:
    print("[FAIL] Product not found")

# Test 2: OpenFoodFacts live lookup
print("\n" + "=" * 60)
print("TEST 2: OpenFoodFacts Live Lookup (Coca-Cola)")
print("=" * 60)
try:
    product_off = lookup_product("5449000000996")
    if product_off:
        print(f"[OK] Found: {product_off.get('name')} (source: {product_off.get('source')})")
        ings = product_off.get('ingredients_text', '')[:100]
        print(f"    Ingredients preview: {ings}...")
    else:
        print("[WARN] Product not found (may be network/API issue)")
except Exception as e:
    print(f"[FAIL] Error: {e}")

# Test 3: Full analysis pipeline
print("\n" + "=" * 60)
print("TEST 3: Full Analysis Pipeline")
print("=" * 60)
try:
    result = analyze_product("8901030895489", {"age": 25, "allergies": [], "conditions": [], "diet": ""})
    if result and not result.get("error"):
        print(f"[OK] Analysis complete")
        print(f"    Product: {result.get('product', {}).get('name')}")
        print(f"    Ingredients: {len(result.get('ingredients', []))}")
        print(f"    Concern Score: {result.get('concern_score', {}).get('score')}")
        print(f"    Level: {result.get('concern_score', {}).get('level')}")
        print(f"    Allergens: {len(result.get('allergens', []))}")
        print(f"    Regulatory: {len(result.get('regulatory', []))}")
        print(f"    AI Summary available: {bool(result.get('ai_summary'))}")
        ds = result.get('dataset_regulatory_report')
        if ds:
            print(f"    Dataset report: {ds.get('summary', {}).get('total')} rows")
    else:
        print(f"[FAIL] Analysis failed: {result.get('error')}")
except Exception as e:
    import traceback
    print(f"[FAIL] Error: {e}")
    traceback.print_exc()

# Test 4: Parse ingredients
print("\n" + "=" * 60)
print("TEST 4: Ingredient Parsing")
print("=" * 60)
sample = "wheat flour, refined palm oil, salt, flavour enhancer (monosodium glutamate), spices"
ings = parse_ingredients(sample)
print(f"[OK] Parsed {len(ings)} ingredients: {ings}")

# Test 5: Banned ingredients
print("\n" + "=" * 60)
print("TEST 5: Risk Engine")
print("=" * 60)
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
banned_path = os.path.join(data_dir, "banned_ingredients.csv")
if os.path.exists(banned_path):
    banned_df = load_banned_ingredients(banned_path)
    risks = check_banned_ingredients(ings, banned_df)
    print(f"[OK] Risk check complete. {len(risks)} risks found.")
    for r in risks:
        print(f"    - {r.get('ingredient')}: {r.get('risk_level')}")
else:
    print(f"[WARN] Banned ingredients CSV not found at {banned_path}")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETE")
print("=" * 60)