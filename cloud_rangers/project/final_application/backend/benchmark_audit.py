import json, os, sys, time
import requests
from typing import List, Dict

# Define benchmark barcodes (sample set). For demonstration, a few known barcodes are used.
# In practice, extend to 100 barcodes (50 Indian, 50 International).
INDIAN_BARCODES = [
    "8901030895487",  # Sample Indian product (e.g., Amul butter)
    "8901234567890",  # Placeholder Indian
    "8901047168375",  # Sample Indian
]
INTERNATIONAL_BARCODES = [
    "012345678905",  # Sample US product (e.g., Coca-Cola)
    "036000291452",  # Sample US product (e.g., Kellogg's)
    "4006381333901",  # Sample European product (e.g., Haribo)
]

ALL_BARCODES = [("Indian", b) for b in INDIAN_BARCODES] + [("International", b) for b in INTERNATIONAL_BARCODES]

API_BASE = "http://127.0.0.1:8000"

def fetch_local_analysis(barcode: str) -> Dict:
    try:
        r = requests.get(f"{API_BASE}/api/v1/products/{barcode}/analysis", timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def query_openfoodfacts(barcode: str) -> Dict:
    try:
        r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json", timeout=10)
        data = r.json()
        return {"found": data.get("status") == 1, "product": data.get("product")}
    except Exception as e:
        return {"error": str(e)}

def query_usda(barcode: str) -> Dict:
    # USDA API requires an API key; use a public endpoint if available, otherwise mark as not found.
    return {"found": False, "note": "USDA API not configured"}

def assess_barcode(entry):
    region, barcode = entry
    local = fetch_local_analysis(barcode)
    local_found = local.get("product_found", False)
    # Determine if fallback was triggered based on presence of 'fallback_used' flag if exists
    fallback = local.get("fallback_used", False)
    # External providers
    off = query_openfoodfacts(barcode)
    off_found = off.get("found", False)
    usda = query_usda(barcode)
    usda_found = usda.get("found", False)
    # Six factor analysis availability
    six_factor = bool(local.get("six_factor_payload"))
    # Source attribution availability (simple heuristic: presence of 'source' field)
    source_attribution = bool(local.get("source"))
    return {
        "region": region,
        "barcode": barcode,
        "local_found": local_found,
        "off_found": off_found,
        "usda_found": usda_found,
        "fallback": fallback,
        "six_factor": six_factor,
        "source_attribution": source_attribution,
        "local_response": local,
    }

def run_audit():
    results = [assess_barcode(entry) for entry in ALL_BARCODES]
    # Summarize Phase 1
    total = len(results)
    found = sum(r["local_found"] for r in results)
    not_found = total - found
    coverage_pct = (found / total) * 100 if total else 0
    fallback_cnt = sum(r["fallback"] for r in results)
    fallback_pct = (fallback_cnt / total) * 100 if total else 0
    source_attr_cnt = sum(r["source_attribution"] for r in results)
    source_attr_pct = (source_attr_cnt / total) * 100 if total else 0
    print("## BARCODE COVERAGE REPORT")
    print(f"Total Tested: {total}")
    print(f"Found: {found}")
    print(f"Not Found: {not_found}")
    print(f"Coverage %: {coverage_pct:.2f}%")
    print(f"Fallback %: {fallback_pct:.2f}%")
    print(f"Source Attribution %: {source_attr_pct:.2f}%")
    # Detailed JSON output for further phases (placeholder)
    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_audit()
