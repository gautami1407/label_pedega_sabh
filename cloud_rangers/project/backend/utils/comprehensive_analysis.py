"""
Comprehensive Ingredient Analysis Engine
==========================================
Implements the full specification for ingredient analysis:

1. Builds final merged ingredient list from all OFF sources
2. Normalizes all ingredient names (E102/INS102/Tartrazine → Tartrazine)
3. Checks every ingredient against Regulatory Intelligence Database
4. Determines regulatory status per country
5. Calculates Concern Score with weighted factors
6. Generates structured report with banned/restricted/warning sections
7. Produces professional ingredient information cards
"""

import os
import sys
import re
import logging
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_processor import (
    merge_ingredients_and_additives,
    resolve_additive_code,
    parse_ingredients,
    _ADDITIVE_CODE_MAP,
)
from utils.risk_engine import load_banned_ingredients, check_banned_ingredients

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BACKEND_DIR, "data")

# ═══════════════════════════════════════════════════════════════════════════════
# REGULATORY INTELLIGENCE DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

# Comprehensive regulatory database with per-country status
# Structure: normalized_ingredient_name -> { country -> status }
# Status values: "Permitted", "Restricted", "Banned", "Warning Required", "Not Approved", "Information Only"

REGULATORY_DATABASE = {
    # ── Colours ──────────────────────────────────────────────────────────────
    "tartrazine": {
        "name": "Tartrazine",
        "ins": "INS102", "e": "E102",
        "purpose": "Synthetic yellow colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Snacks", "Sauces", "Desserts"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific", "India": "Category-specific"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2009; 1073, JECFA 67th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Warning Required",
            "UK": "Warning Required", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Norway": "Banned",
            "Finland": "Banned", "Brazil": "Permitted", "China": "Permitted"
        }
    },
    "sunset yellow fcf": {
        "name": "Sunset Yellow FCF",
        "ins": "INS110", "e": "E110",
        "purpose": "Synthetic orange-yellow colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Snacks", "Sauces", "Desserts"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2009; 1073, JECFA 67th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Warning Required",
            "UK": "Warning Required", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Norway": "Banned",
            "Finland": "Banned", "Brazil": "Permitted", "China": "Permitted"
        }
    },
    "allura red ac": {
        "name": "Allura Red AC",
        "ins": "INS129", "e": "E129",
        "purpose": "Synthetic red colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Snacks", "Desserts"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2009; 1073, JECFA 67th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Warning Required",
            "UK": "Warning Required", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Norway": "Banned",
            "Finland": "Banned", "Brazil": "Permitted", "China": "Permitted"
        }
    },
    "quinoline yellow": {
        "name": "Quinoline Yellow",
        "ins": "INS104", "e": "E104",
        "purpose": "Synthetic yellow-green colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Snacks"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008",
        "reference": "EFSA Journal 2009; 1073",
        "countries": {
            "India": "Permitted", "USA": "Not Approved", "EU": "Warning Required",
            "UK": "Warning Required", "Canada": "Not Approved", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Norway": "Banned",
            "Finland": "Banned", "Brazil": "Not Approved", "China": "Not Approved"
        }
    },
    "carmoisine": {
        "name": "Carmoisine",
        "ins": "INS122", "e": "E122",
        "purpose": "Synthetic red colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Desserts"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008",
        "reference": "EFSA Journal 2009; 1073",
        "countries": {
            "India": "Permitted", "USA": "Not Approved", "EU": "Warning Required",
            "UK": "Warning Required", "Canada": "Not Approved", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Norway": "Banned",
            "Finland": "Banned", "Brazil": "Not Approved", "China": "Not Approved"
        }
    },
    "ponceau 4r": {
        "name": "Ponceau 4R",
        "ins": "INS124", "e": "E124",
        "purpose": "Synthetic red colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Desserts"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008",
        "reference": "EFSA Journal 2009; 1073",
        "countries": {
            "India": "Permitted", "USA": "Not Approved", "EU": "Warning Required",
            "UK": "Warning Required", "Canada": "Not Approved", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Norway": "Banned",
            "Finland": "Banned", "Brazil": "Not Approved", "China": "Not Approved"
        }
    },
    "brilliant blue fcf": {
        "name": "Brilliant Blue FCF",
        "ins": "INS133", "e": "E133",
        "purpose": "Synthetic blue colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Desserts"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2009; 1073, JECFA 67th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Not Approved",
            "UK": "Not Approved", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "indigotine": {
        "name": "Indigotine",
        "ins": "INS132", "e": "E132",
        "purpose": "Synthetic blue colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Desserts"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2009; 1073, JECFA 67th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Not Approved",
            "UK": "Not Approved", "Canada": "Permitted", "Australia": "Not Approved",
            "Japan": "Not Approved", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "titanium dioxide": {
        "name": "Titanium Dioxide",
        "ins": "INS171", "e": "E171",
        "purpose": "White colouring agent (opacifier)",
        "food_categories": ["Confectionery", "Chewing gum", "Sauces", "Dressings", "Bakery"],
        "max_limits": {"EU": "Not Authorized", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008 (amended 2022), FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2021; 19(5):6585, EMA/CHMP/331973/2021",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Banned",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "France": "Banned",
            "Brazil": "Permitted", "China": "Permitted"
        }
    },
    "erythrosine": {
        "name": "Erythrosine",
        "ins": "INS127", "e": "E127",
        "purpose": "Synthetic red colouring agent",
        "food_categories": ["Confectionery", "Maraschino cherries", "Snacks"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008",
        "reference": "EFSA Journal 2009; 1073",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Restricted",
            "UK": "Restricted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "amaranth": {
        "name": "Amaranth",
        "ins": "INS123", "e": "E123",
        "purpose": "Synthetic red colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Snacks"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008",
        "reference": "EFSA Journal 2009; 1073",
        "countries": {
            "India": "Permitted", "USA": "Not Approved", "EU": "Restricted",
            "UK": "Restricted", "Canada": "Not Approved", "Australia": "Not Approved",
            "Japan": "Not Approved", "Singapore": "Not Approved", "Brazil": "Not Approved",
            "China": "Not Approved"
        }
    },
    "patent blue v": {
        "name": "Patent Blue V",
        "ins": "INS131", "e": "E131",
        "purpose": "Synthetic blue colouring agent",
        "food_categories": ["Beverages", "Confectionery", "Desserts"],
        "max_limits": {"EU": "Category-specific (10-500 mg/kg)", "UK": "Category-specific"},
        "regulation": "EU Regulation 1333/2008",
        "reference": "EFSA Journal 2009; 1073",
        "countries": {
            "India": "Not Approved", "USA": "Not Approved", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Not Approved", "Australia": "Not Approved",
            "Japan": "Not Approved", "Singapore": "Not Approved", "Brazil": "Not Approved",
            "China": "Not Approved"
        }
    },
    "caramel colour iv": {
        "name": "Caramel Colour IV",
        "ins": "INS150d", "e": "E150d",
        "purpose": "Brown colouring agent (ammonia-sulfite process)",
        "food_categories": ["Beverages", "Sauces", "Confectionery", "Bakery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2011; 9(3):2004, California Prop 65",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    # ── Preservatives ────────────────────────────────────────────────────────
    "sodium benzoate": {
        "name": "Sodium Benzoate",
        "ins": "INS211", "e": "E211",
        "purpose": "Synthetic preservative (antimicrobial)",
        "food_categories": ["Beverages", "Sauces", "Pickles", "Jams", "Margarine"],
        "max_limits": {"EU": "150-600 mg/kg", "UK": "150-600 mg/kg", "India": "150-600 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2016; 14(8):4562, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "potassium sorbate": {
        "name": "Potassium Sorbate",
        "ins": "INS202", "e": "E202",
        "purpose": "Synthetic preservative (antimicrobial)",
        "food_categories": ["Beverages", "Dairy", "Bakery", "Sauces", "Wine"],
        "max_limits": {"EU": "200-2000 mg/kg", "UK": "200-2000 mg/kg", "India": "200-2000 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2015; 13(6):4144, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "sodium nitrite": {
        "name": "Sodium Nitrite",
        "ins": "INS250", "e": "E250",
        "purpose": "Preservative and colour fixative in cured meats",
        "food_categories": ["Cured meats", "Sausages", "Bacon", "Ham", "Pâté"],
        "max_limits": {"EU": "50-150 mg/kg", "UK": "50-150 mg/kg", "India": "50-150 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, IARC Monograph 94",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Restricted",
            "UK": "Restricted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "sodium nitrate": {
        "name": "Sodium Nitrate",
        "ins": "INS251", "e": "E251",
        "purpose": "Preservative and colour fixative in cured meats",
        "food_categories": ["Cured meats", "Cheese", "Fish products"],
        "max_limits": {"EU": "50-150 mg/kg", "UK": "50-150 mg/kg", "India": "50-150 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, IARC Monograph 94",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Restricted",
            "UK": "Restricted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "sulphur dioxide": {
        "name": "Sulphur Dioxide",
        "ins": "INS220", "e": "E220",
        "purpose": "Preservative and antioxidant",
        "food_categories": ["Dried fruits", "Wine", "Beverages", "Sauces", "Pickles"],
        "max_limits": {"EU": "10-2000 mg/kg", "UK": "10-2000 mg/kg", "India": "10-2000 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2016; 14(4):4438, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "potassium bromate": {
        "name": "Potassium Bromate",
        "ins": "INS924a", "e": "E924a",
        "purpose": "Flour treatment agent (improver)",
        "food_categories": ["Bakery", "Bread", "Flour"],
        "max_limits": {"EU": "Not Authorized", "UK": "Not Authorized", "India": "Not Authorized"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "IARC Monograph 73, JECFA 61st report",
        "countries": {
            "India": "Banned", "USA": "Not Approved", "EU": "Banned",
            "UK": "Banned", "Canada": "Banned", "Australia": "Banned",
            "Japan": "Banned", "Singapore": "Banned", "Brazil": "Banned",
            "China": "Banned", "Nigeria": "Banned", "Sri Lanka": "Banned"
        }
    },
    "brominated vegetable oil": {
        "name": "Brominated Vegetable Oil",
        "ins": "—", "e": "—",
        "purpose": "Emulsifier and stabiliser in citrus beverages",
        "food_categories": ["Citrus beverages", "Soft drinks"],
        "max_limits": {"EU": "Not Authorized", "UK": "Not Authorized", "India": "Not Authorized"},
        "regulation": "FSSAI Food Additive Regulations, FDA 21 CFR 180.30",
        "reference": "EFSA Journal 2012; 10(12):2961, JECFA 76th report",
        "countries": {
            "India": "Banned", "USA": "Restricted", "EU": "Banned",
            "UK": "Banned", "Canada": "Banned", "Australia": "Banned",
            "Japan": "Banned", "Singapore": "Banned", "Brazil": "Banned",
            "China": "Banned"
        }
    },
    "azodicarbonamide": {
        "name": "Azodicarbonamide",
        "ins": "INS927a", "e": "E927a",
        "purpose": "Flour treatment agent (bleaching/improver)",
        "food_categories": ["Bakery", "Bread", "Buns"],
        "max_limits": {"EU": "Not Authorized", "UK": "Not Authorized", "India": "Not Authorized"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2005; 3(1):1, JECFA 65th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Banned",
            "UK": "Banned", "Canada": "Banned", "Australia": "Banned",
            "Japan": "Banned", "Singapore": "Banned", "Brazil": "Banned",
            "China": "Banned"
        }
    },
    # ── Antioxidants ─────────────────────────────────────────────────────────
    "bha": {
        "name": "BHA",
        "ins": "INS320", "e": "E320",
        "purpose": "Synthetic antioxidant (preserves fats)",
        "food_categories": ["Fats & oils", "Snacks", "Cereals", "Chewing gum"],
        "max_limits": {"EU": "200 mg/kg (fat basis)", "UK": "200 mg/kg", "India": "200 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2011; 9(5):2187, IARC Monograph 40",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Restricted",
            "UK": "Restricted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Restricted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "bht": {
        "name": "BHT",
        "ins": "INS321", "e": "E321",
        "purpose": "Synthetic antioxidant (preserves fats)",
        "food_categories": ["Fats & oils", "Snacks", "Cereals", "Chewing gum"],
        "max_limits": {"EU": "200 mg/kg (fat basis)", "UK": "200 mg/kg", "India": "200 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2012; 10(1):2520, IARC Monograph 40",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Restricted",
            "UK": "Restricted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Restricted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "tbhq": {
        "name": "TBHQ",
        "ins": "INS319", "e": "E319",
        "purpose": "Synthetic antioxidant (preserves fats)",
        "food_categories": ["Fats & oils", "Snacks", "Frozen foods"],
        "max_limits": {"EU": "200 mg/kg (fat basis)", "UK": "200 mg/kg", "India": "200 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2004; 2(1):1, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "propyl gallate": {
        "name": "Propyl Gallate",
        "ins": "INS310", "e": "E310",
        "purpose": "Synthetic antioxidant (preserves fats)",
        "food_categories": ["Fats & oils", "Snacks", "Meat products"],
        "max_limits": {"EU": "200 mg/kg (fat basis)", "UK": "200 mg/kg"},
        "regulation": "EU Regulation 1333/2008",
        "reference": "EFSA Journal 2014; 12(4):3642, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Not Approved",
            "UK": "Not Approved", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    # ── Sweeteners ───────────────────────────────────────────────────────────
    "aspartame": {
        "name": "Aspartame",
        "ins": "INS951", "e": "E951",
        "purpose": "Intense artificial sweetener",
        "food_categories": ["Diet beverages", "Sugar-free products", "Desserts", "Chewing gum"],
        "max_limits": {"EU": "600-5500 mg/kg", "UK": "600-5500 mg/kg", "India": "600-5500 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2013; 11(12):3496, IARC Monograph 2023 (Group 2B)",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "saccharin": {
        "name": "Saccharin",
        "ins": "INS954", "e": "E954",
        "purpose": "Intense artificial sweetener",
        "food_categories": ["Diet beverages", "Table-top sweeteners", "Desserts"],
        "max_limits": {"EU": "80-1200 mg/kg", "UK": "80-1200 mg/kg", "India": "80-1200 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2016; 14(12):4592, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Restricted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "sucralose": {
        "name": "Sucralose",
        "ins": "INS955", "e": "E955",
        "purpose": "Intense artificial sweetener",
        "food_categories": ["Diet beverages", "Bakery", "Desserts", "Sauces"],
        "max_limits": {"EU": "200-3200 mg/kg", "UK": "200-3200 mg/kg", "India": "200-3200 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2016; 14(12):4592, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "acesulfame potassium": {
        "name": "Acesulfame Potassium",
        "ins": "INS950", "e": "E950",
        "purpose": "Intense artificial sweetener",
        "food_categories": ["Diet beverages", "Desserts", "Confectionery", "Dairy"],
        "max_limits": {"EU": "250-3500 mg/kg", "UK": "250-3500 mg/kg", "India": "250-3500 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2016; 14(12):4592, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "cyclamates": {
        "name": "Cyclamates",
        "ins": "INS952", "e": "E952",
        "purpose": "Intense artificial sweetener",
        "food_categories": ["Diet beverages", "Table-top sweeteners", "Desserts"],
        "max_limits": {"EU": "250-4000 mg/kg", "UK": "250-4000 mg/kg"},
        "regulation": "EU Regulation 1333/2008",
        "reference": "EFSA Journal 2016; 14(12):4592, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Not Approved", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Not Approved", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    # ── Flavour Enhancers ────────────────────────────────────────────────────
    "monosodium glutamate": {
        "name": "Monosodium Glutamate",
        "ins": "INS621", "e": "E621",
        "purpose": "Flavour enhancer (umami)",
        "food_categories": ["Snacks", "Sauces", "Instant noodles", "Seasonings", "Processed meats"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report, FDA GRAS",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    # ── Emulsifiers / Stabilisers ────────────────────────────────────────────
    "carrageenan": {
        "name": "Carrageenan",
        "ins": "INS407", "e": "E407",
        "purpose": "Thickener, stabiliser, and gelling agent",
        "food_categories": ["Dairy", "Plant-based milk", "Desserts", "Sauces", "Meat products"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2018; 16(4):5238, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "pgpr": {
        "name": "PGPR",
        "ins": "INS476", "e": "E476",
        "purpose": "Emulsifier (reduces viscosity in chocolate)",
        "food_categories": ["Chocolate", "Confectionery", "Margarine"],
        "max_limits": {"EU": "5000 mg/kg (chocolate)", "UK": "5000 mg/kg", "India": "5000 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    # ── Trans Fats ───────────────────────────────────────────────────────────
    "partially hydrogenated oil": {
        "name": "Partially Hydrogenated Oil",
        "ins": "—", "e": "—",
        "purpose": "Source of trans fats (texture/stability)",
        "food_categories": ["Bakery", "Margarine", "Snacks", "Fried foods"],
        "max_limits": {"EU": "2g/100g fat (max)", "UK": "2g/100g fat", "India": "Not Regulated"},
        "regulation": "EU Regulation 2019/649, FDA Final Determination 2018",
        "reference": "FDA 2018 Final Determination, WHO REPLACE initiative",
        "countries": {
            "India": "Permitted", "USA": "Banned", "EU": "Banned",
            "UK": "Banned", "Canada": "Banned", "Australia": "Banned",
            "Japan": "Permitted", "Singapore": "Banned", "Brazil": "Banned",
            "China": "Permitted"
        }
    },
    # ── Common food ingredients ──────────────────────────────────────────────
    "sugar": {
        "name": "Sugar",
        "ins": "—", "e": "—",
        "purpose": "Sweetener and preservative",
        "food_categories": ["All food categories"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "WHO Sugar Guidelines 2015, FSSAI Labelling Regulations",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "salt": {
        "name": "Salt",
        "ins": "—", "e": "—",
        "purpose": "Seasoning and preservative",
        "food_categories": ["All food categories"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "WHO Sodium Guidelines, FSSAI Labelling Regulations",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "palm oil": {
        "name": "Palm Oil",
        "ins": "—", "e": "—",
        "purpose": "Vegetable oil (cooking and manufacturing)",
        "food_categories": ["Snacks", "Bakery", "Margarine", "Confectionery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Labelling Regulations, EU Food Information Regulation",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "phosphoric acid": {
        "name": "Phosphoric Acid",
        "ins": "INS338", "e": "E338",
        "purpose": "Acidity regulator and sequestrant",
        "food_categories": ["Beverages", "Jams", "Processed meats", "Cheese"],
        "max_limits": {"EU": "Category-specific (500-5000 mg/kg)", "UK": "Category-specific", "India": "Category-specific"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2013; 11(6):3245, JECFA 37th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "caffeine": {
        "name": "Caffeine",
        "ins": "—", "e": "—",
        "purpose": "Stimulant (flavouring agent)",
        "food_categories": ["Beverages", "Energy drinks", "Confectionery"],
        "max_limits": {"EU": "150 mg/L (energy drinks)", "UK": "150 mg/L", "India": "145 mg/L"},
        "regulation": "EU Regulation 1169/2011, FSSAI Labelling Regulations",
        "reference": "EFSA Journal 2015; 13(5):4102, FSSAI 2018 Regulations",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "soy lecithin": {
        "name": "Soy Lecithin",
        "ins": "INS322", "e": "E322",
        "purpose": "Emulsifier and stabiliser",
        "food_categories": ["Chocolate", "Bakery", "Margarine", "Confectionery"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "mono- and diglycerides": {
        "name": "Mono- and Diglycerides",
        "ins": "INS471", "e": "E471",
        "purpose": "Emulsifier and stabiliser",
        "food_categories": ["Bakery", "Margarine", "Ice cream", "Confectionery"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "xanthan gum": {
        "name": "Xanthan Gum",
        "ins": "INS415", "e": "E415",
        "purpose": "Thickener and stabiliser",
        "food_categories": ["Sauces", "Dressings", "Bakery", "Beverages", "Dairy"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "citric acid": {
        "name": "Citric Acid",
        "ins": "INS330", "e": "E330",
        "purpose": "Acidity regulator and preservative",
        "food_categories": ["Beverages", "Jams", "Confectionery", "Dairy", "Sauces"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "guar gum": {
        "name": "Guar Gum",
        "ins": "INS412", "e": "E412",
        "purpose": "Thickener and stabiliser",
        "food_categories": ["Sauces", "Dairy", "Bakery", "Beverages"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "gelatin": {
        "name": "Gelatin",
        "ins": "—", "e": "—",
        "purpose": "Gelling agent and thickener (animal-derived)",
        "food_categories": ["Desserts", "Confectionery", "Dairy", "Meat products"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards, EU Food Information Regulation",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "wheat flour": {
        "name": "Wheat Flour",
        "ins": "—", "e": "—",
        "purpose": "Base ingredient (carbohydrate source)",
        "food_categories": ["Bakery", "Pasta", "Snacks", "Noodles"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards, Codex Alimentarius",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "refined palm oil": {
        "name": "Refined Palm Oil",
        "ins": "—", "e": "—",
        "purpose": "Vegetable oil (cooking and manufacturing)",
        "food_categories": ["Snacks", "Bakery", "Margarine", "Confectionery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Labelling Regulations, EU Food Information Regulation",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "spices": {
        "name": "Spices",
        "ins": "—", "e": "—",
        "purpose": "Flavouring agent",
        "food_categories": ["All food categories"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Spices Regulations, Codex Alimentarius",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "flavour enhancer (monosodium glutamate)": {
        "name": "Monosodium Glutamate",
        "ins": "INS621", "e": "E621",
        "purpose": "Flavour enhancer (umami)",
        "food_categories": ["Snacks", "Sauces", "Instant noodles", "Seasonings", "Processed meats"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report, FDA GRAS",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "onion powder": {
        "name": "Onion Powder",
        "ins": "—", "e": "—",
        "purpose": "Natural flavouring agent",
        "food_categories": ["Seasonings", "Snacks", "Sauces", "Ready meals"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "turmeric": {
        "name": "Turmeric",
        "ins": "—", "e": "—",
        "purpose": "Natural colouring and flavouring agent",
        "food_categories": ["Seasonings", "Sauces", "Snacks", "Ready meals"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards, Codex Alimentarius",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "carbonated water": {
        "name": "Carbonated Water",
        "ins": "—", "e": "—",
        "purpose": "Base ingredient (beverage base)",
        "food_categories": ["Beverages"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "natural flavourings": {
        "name": "Natural Flavourings",
        "ins": "—", "e": "—",
        "purpose": "Natural flavouring agent",
        "food_categories": ["Beverages", "Confectionery", "Snacks", "Dairy"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1334/2008, FSSAI Food Safety Standards",
        "reference": "EFSA Journal, FEMA GRAS list",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "cocoa butter": {
        "name": "Cocoa Butter",
        "ins": "—", "e": "—",
        "purpose": "Fat source (chocolate manufacturing)",
        "food_categories": ["Chocolate", "Confectionery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards, Codex Alimentarius",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "skimmed milk powder": {
        "name": "Skimmed Milk Powder",
        "ins": "—", "e": "—",
        "purpose": "Dairy ingredient (protein and solids)",
        "food_categories": ["Dairy", "Chocolate", "Bakery", "Confectionery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Milk Product Standards, Codex Alimentarius",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "cocoa mass": {
        "name": "Cocoa Mass",
        "ins": "—", "e": "—",
        "purpose": "Base ingredient (chocolate manufacturing)",
        "food_categories": ["Chocolate", "Confectionery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards, Codex Alimentarius",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "milk fat": {
        "name": "Milk Fat",
        "ins": "—", "e": "—",
        "purpose": "Dairy fat source",
        "food_categories": ["Dairy", "Chocolate", "Bakery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Milk Product Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "lactose": {
        "name": "Lactose",
        "ins": "—", "e": "—",
        "purpose": "Dairy sugar (sweetener and bulking agent)",
        "food_categories": ["Dairy", "Confectionery", "Bakery", "Pharmaceutical"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "vanillin": {
        "name": "Vanillin",
        "ins": "—", "e": "—",
        "purpose": "Synthetic flavouring agent (vanilla flavour)",
        "food_categories": ["Confectionery", "Bakery", "Dairy", "Beverages"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1334/2008, FSSAI Food Safety Standards",
        "reference": "EFSA Journal, FEMA GRAS list",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "dried potatoes": {
        "name": "Dried Potatoes",
        "ins": "—", "e": "—",
        "purpose": "Base ingredient (carbohydrate source)",
        "food_categories": ["Snacks", "Ready meals"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "vegetable oil": {
        "name": "Vegetable Oil",
        "ins": "—", "e": "—",
        "purpose": "Fat source (cooking and manufacturing)",
        "food_categories": ["All food categories"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "rice flour": {
        "name": "Rice Flour",
        "ins": "—", "e": "—",
        "purpose": "Base ingredient (carbohydrate source)",
        "food_categories": ["Bakery", "Snacks", "Noodles"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "wheat starch": {
        "name": "Wheat Starch",
        "ins": "—", "e": "—",
        "purpose": "Thickener and stabiliser",
        "food_categories": ["Bakery", "Snacks", "Sauces"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "maltodextrin": {
        "name": "Maltodextrin",
        "ins": "—", "e": "—",
        "purpose": "Bulking agent and sweetener",
        "food_categories": ["Snacks", "Beverages", "Confectionery", "Sports nutrition"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards, FDA GRAS",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "emulsifier (e471)": {
        "name": "Mono- and Diglycerides",
        "ins": "INS471", "e": "E471",
        "purpose": "Emulsifier and stabiliser",
        "food_categories": ["Bakery", "Margarine", "Ice cream", "Confectionery"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "invert syrup": {
        "name": "Invert Syrup",
        "ins": "—", "e": "—",
        "purpose": "Sweetener and humectant",
        "food_categories": ["Confectionery", "Bakery", "Beverages"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "leavening agents": {
        "name": "Leavening Agents",
        "ins": "—", "e": "—",
        "purpose": "Raising agent (baking)",
        "food_categories": ["Bakery", "Snacks"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "milk solids": {
        "name": "Milk Solids",
        "ins": "—", "e": "—",
        "purpose": "Dairy ingredient (protein and solids)",
        "food_categories": ["Dairy", "Chocolate", "Bakery", "Confectionery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Milk Product Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "dextrose": {
        "name": "Dextrose",
        "ins": "—", "e": "—",
        "purpose": "Sweetener (simple sugar)",
        "food_categories": ["Confectionery", "Bakery", "Beverages", "Sports nutrition"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "edible vegetable oil": {
        "name": "Edible Vegetable Oil",
        "ins": "—", "e": "—",
        "purpose": "Fat source (cooking and manufacturing)",
        "food_categories": ["All food categories"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "General food safety regulations",
        "reference": "FSSAI Food Safety Standards",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "colour (caramel e150d)": {
        "name": "Caramel Colour IV",
        "ins": "INS150d", "e": "E150d",
        "purpose": "Brown colouring agent (ammonia-sulfite process)",
        "food_categories": ["Beverages", "Sauces", "Confectionery", "Bakery"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2011; 9(3):2004, California Prop 65",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "natural flavourings including caffeine": {
        "name": "Natural Flavourings",
        "ins": "—", "e": "—",
        "purpose": "Natural flavouring agent",
        "food_categories": ["Beverages", "Confectionery", "Snacks", "Dairy"],
        "max_limits": {"EU": "Quantum satis (GMP)", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1334/2008, FSSAI Food Safety Standards",
        "reference": "EFSA Journal, FEMA GRAS list",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "polyglycerol polyricinoleate": {
        "name": "PGPR",
        "ins": "INS476", "e": "E476",
        "purpose": "Emulsifier (reduces viscosity in chocolate)",
        "food_categories": ["Chocolate", "Confectionery", "Margarine"],
        "max_limits": {"EU": "5000 mg/kg (chocolate)", "UK": "5000 mg/kg", "India": "5000 mg/kg"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2017; 15(6):4786, JECFA 69th report",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
    "caramel e150a": {
        "name": "Caramel (plain)",
        "ins": "INS150a", "e": "E150a",
        "purpose": "Brown colouring agent (plain caramel)",
        "food_categories": ["Confectionery", "Bakery", "Beverages", "Sauces"],
        "max_limits": {"EU": "Quantum satis", "UK": "Quantum satis", "India": "Quantum satis"},
        "regulation": "EU Regulation 1333/2008, FSSAI Food Additive Regulations",
        "reference": "EFSA Journal 2011; 9(3):2004",
        "countries": {
            "India": "Permitted", "USA": "Permitted", "EU": "Permitted",
            "UK": "Permitted", "Canada": "Permitted", "Australia": "Permitted",
            "Japan": "Permitted", "Singapore": "Permitted", "Brazil": "Permitted",
            "China": "Permitted"
        }
    },
}

# Build normalized lookup index
_NORMALIZED_LOOKUP = {}
for key, data in REGULATORY_DATABASE.items():
    _NORMALIZED_LOOKUP[key] = data
    # Also index by INS and E numbers
    if data.get("ins") and data["ins"] != "—":
        _NORMALIZED_LOOKUP[data["ins"].lower().replace(" ", "")] = data
    if data.get("e") and data["e"] != "—":
        _NORMALIZED_LOOKUP[data["e"].lower().replace(" ", "")] = data
    # Index by name
    name_lower = data["name"].lower()
    if name_lower != key:
        _NORMALIZED_LOOKUP[name_lower] = data


def normalize_ingredient_name(name: str) -> str:
    """
    Normalize an ingredient name to its canonical form.
    Handles E numbers, INS numbers, and common aliases.
    """
    if not name:
        return ""
    
    cleaned = name.strip().lower()
    
    # Try direct lookup in the additive code map
    resolved = resolve_additive_code(cleaned)
    if resolved:
        return resolved["ingredient_name"]
    
    # Try lookup in the regulatory database
    if cleaned in _NORMALIZED_LOOKUP:
        return _NORMALIZED_LOOKUP[cleaned]["name"]
    
    # Try partial match
    for key, data in _NORMALIZED_LOOKUP.items():
        if cleaned in key or key in cleaned:
            return data["name"]
    
    # Return title-cased version
    return name.strip().title()


def lookup_ingredient_regulatory(ingredient_name: str) -> Optional[Dict]:
    """
    Look up an ingredient in the Regulatory Intelligence Database.
    Returns the full regulatory record or None if not found.
    """
    if not ingredient_name:
        return None
    
    cleaned = ingredient_name.strip().lower()
    
    # Direct lookup
    if cleaned in _NORMALIZED_LOOKUP:
        return _NORMALIZED_LOOKUP[cleaned]
    
    # Try resolving as additive code first
    resolved = resolve_additive_code(cleaned)
    if resolved:
        resolved_name = resolved["ingredient_name"].lower()
        if resolved_name in _NORMALIZED_LOOKUP:
            return _NORMALIZED_LOOKUP[resolved_name]
    
    # Partial match
    for key, data in _NORMALIZED_LOOKUP.items():
        if cleaned in key or key in cleaned:
            return data
    
    return None


def determine_regulatory_status(reg_record: Dict) -> Dict:
    """
    Determine the overall regulatory status for an ingredient.
    Returns categorized countries and overall status.
    """
    if not reg_record or "countries" not in reg_record:
        return {
            "overall_status": "Information Only",
            "permitted_countries": [],
            "restricted_countries": [],
            "banned_countries": [],
            "warning_required_countries": [],
            "not_approved_countries": [],
            "all_countries": []
        }
    
    countries = reg_record["countries"]
    permitted = []
    restricted = []
    banned = []
    warning_required = []
    not_approved = []
    all_countries = []
    
    for country, status in countries.items():
        entry = {"country": country, "status": status}
        all_countries.append(entry)
        if status == "Permitted":
            permitted.append(entry)
        elif status == "Restricted":
            restricted.append(entry)
        elif status == "Banned":
            banned.append(entry)
        elif status == "Warning Required":
            warning_required.append(entry)
        elif status == "Not Approved":
            not_approved.append(entry)
        else:
            permitted.append(entry)  # Default to permitted
    
    # Determine overall status
    if banned:
        overall = "Banned"
    elif restricted:
        overall = "Restricted"
    elif warning_required:
        overall = "Warning Required"
    elif not_approved:
        overall = "Restricted"
    else:
        overall = "Permitted"
    
    return {
        "overall_status": overall,
        "permitted_countries": permitted,
        "restricted_countries": restricted,
        "banned_countries": banned,
        "warning_required_countries": warning_required,
        "not_approved_countries": not_approved,
        "all_countries": all_countries
    }


def calculate_concern_score_v2(
    banned_count: int,
    restricted_count: int,
    warning_count: int,
    high_toxicity: bool = False,
    is_contaminant: bool = False,
    is_major_allergen: bool = False,
    user_specific_risk: bool = False
) -> Dict:
    """
    Calculate the concern score using the specified weighting system.
    
    Weighting:
    - Banned Ingredient: +30
    - Restricted Ingredient: +15
    - Warning Label Ingredient: +10
    - High Toxicity: +15
    - Contaminant: +40
    - Major Allergen: +15
    - User-specific Risk: +20
    """
    score = 0
    factors = []
    
    if banned_count > 0:
        score += banned_count * 30
        factors.append(f"{banned_count} banned ingredient(s) (+{banned_count * 30})")
    
    if restricted_count > 0:
        score += restricted_count * 15
        factors.append(f"{restricted_count} restricted ingredient(s) (+{restricted_count * 15})")
    
    if warning_count > 0:
        score += warning_count * 10
        factors.append(f"{warning_count} warning-label ingredient(s) (+{warning_count * 10})")
    
    if high_toxicity:
        score += 15
        factors.append("High toxicity ingredient detected (+15)")
    
    if is_contaminant:
        score += 40
        factors.append("Food contaminant detected (+40)")
    
    if is_major_allergen:
        score += 15
        factors.append("Major allergen present (+15)")
    
    if user_specific_risk:
        score += 20
        factors.append("User-specific health risk (+20)")
    
    # Clamp to 0-100
    score = max(0, min(100, score))
    
    # Determine level
    if score <= 20:
        level = "Very Safe"
    elif score <= 40:
        level = "Low Concern"
    elif score <= 60:
        level = "Moderate Concern"
    elif score <= 80:
        level = "High Concern"
    else:
        level = "Very High Concern"
    
    return {
        "score": score,
        "level": level,
        "factors": factors
    }


def build_ingredient_card(ingredient_name: str, reg_record: Optional[Dict] = None) -> Dict:
    """
    Build a professional ingredient information card.
    """
    if reg_record is None:
        reg_record = lookup_ingredient_regulatory(ingredient_name)
    
    if reg_record is None:
        return {
            "name": ingredient_name,
            "purpose": "Ingredient listed on label.",
            "regulatory_status": "Information Only",
            "risk_level": "Safe",
            "food_categories": [],
            "country_wise_regulatory": [],
            "max_permitted_limits": {},
            "health_effects": "No detailed information available.",
            "scientific_evidence": "No data available.",
            "official_regulations": "General food safety regulations apply.",
            "official_references": "Refer to local food authority.",
            "ins_number": "",
            "e_number": ""
        }
    
    reg_status = determine_regulatory_status(reg_record)
    
    # Determine risk level
    overall = reg_status["overall_status"]
    if overall == "Banned":
        risk_level = "Banned"
    elif overall == "Restricted":
        risk_level = "Restricted"
    elif overall == "Warning Required":
        risk_level = "Warning Required"
    elif reg_record.get("purpose", "").lower() in [
        "synthetic colouring agent", "synthetic preservative",
        "intense artificial sweetener", "synthetic antioxidant"
    ]:
        risk_level = "Moderate Concern"
    else:
        risk_level = "Permitted"
    
    return {
        "name": reg_record.get("name", ingredient_name),
        "purpose": reg_record.get("purpose", "Ingredient listed on label."),
        "regulatory_status": overall,
        "risk_level": risk_level,
        "food_categories": reg_record.get("food_categories", []),
        "country_wise_regulatory": reg_status["all_countries"],
        "permitted_countries": [c["country"] for c in reg_status["permitted_countries"]],
        "restricted_countries": [c["country"] for c in reg_status["restricted_countries"]],
        "banned_countries": [c["country"] for c in reg_status["banned_countries"]],
        "warning_required_countries": [c["country"] for c in reg_status["warning_required_countries"]],
        "not_approved_countries": [c["country"] for c in reg_status["not_approved_countries"]],
        "max_permitted_limits": reg_record.get("max_limits", {}),
        "health_effects": _get_health_effects(ingredient_name, reg_record),
        "scientific_evidence": _get_scientific_evidence(ingredient_name, reg_record),
        "official_regulations": reg_record.get("regulation", "General food safety regulations apply."),
        "official_references": reg_record.get("reference", "Refer to local food authority."),
        "ins_number": reg_record.get("ins", ""),
        "e_number": reg_record.get("e", "")
    }


def _get_health_effects(ingredient_name: str, reg_record: Dict) -> str:
    """Generate health effects description based on regulatory data."""
    name = reg_record.get("name", ingredient_name)
    purpose = reg_record.get("purpose", "")
    countries = reg_record.get("countries", {})
    
    banned = [c for c, s in countries.items() if s == "Banned"]
    restricted = [c for c, s in countries.items() if s == "Restricted"]
    warning = [c for c, s in countries.items() if s == "Warning Required"]
    
    effects = []
    
    if banned:
        effects.append(f"Banned in {', '.join(banned[:3])}" + 
                       (f" and {len(banned) - 3} other countries" if len(banned) > 3 else "") + 
                       " due to health concerns.")
    
    if restricted:
        effects.append(f"Usage restricted in {', '.join(restricted[:2])}" +
                       (f" and {len(restricted) - 2} other countries" if len(restricted) > 2 else "") +
                       " with maximum permitted limits.")
    
    if warning:
        effects.append(f"Warning labels required in {', '.join(warning[:2])}" +
                       (f" and {len(warning) - 2} other countries" if len(warning) > 2 else "") +
                       ".")
    
    if "colour" in purpose.lower() or "colouring" in purpose.lower():
        effects.append("Some studies suggest potential links to hyperactivity in children.")
    
    if "preservative" in purpose.lower():
        effects.append("Generally recognized as safe at approved levels. May cause sensitivity in some individuals.")
    
    if "sweetener" in purpose.lower():
        effects.append("Approved for use within established acceptable daily intake (ADI) levels.")
    
    if not effects:
        effects.append("Generally recognized as safe when consumed within recommended limits.")
    
    return " ".join(effects)


def _get_scientific_evidence(ingredient_name: str, reg_record: Dict) -> str:
    """Generate scientific evidence summary."""
    reference = reg_record.get("reference", "")
    if reference and reference != "Refer to local food authority.":
        return f"Evaluated by international food safety authorities including {reference}. " \
               "Ongoing research continues to monitor safety profiles."
    return "Evaluated by national and international food safety authorities. " \
           "Generally recognized as safe within approved usage levels."


def analyze_ingredients_comprehensive(
    ingredients: List[str],
    user_profile: Optional[Dict] = None
) -> Dict:
    """
    Perform comprehensive ingredient analysis.
    
    Args:
        ingredients: List of ingredient names (already merged and normalized)
        user_profile: Optional dict with allergies, conditions, diet, age
    
    Returns:
        Complete analysis report
    """
    if user_profile is None:
        user_profile = {}
    
    # Build ingredient cards
    ingredient_cards = []
    for ing in ingredients:
        reg_record = lookup_ingredient_regulatory(ing)
        card = build_ingredient_card(ing, reg_record)
        ingredient_cards.append(card)
    
    # Categorize ingredients
    banned_ingredients = [c for c in ingredient_cards if c["regulatory_status"] == "Banned"]
    restricted_ingredients = [c for c in ingredient_cards if c["regulatory_status"] == "Restricted"]
    warning_ingredients = [c for c in ingredient_cards if c["regulatory_status"] == "Warning Required"]
    permitted_ingredients = [c for c in ingredient_cards if c["regulatory_status"] == "Permitted"]
    info_only_ingredients = [c for c in ingredient_cards if c["regulatory_status"] == "Information Only"]
    
    # Detect major allergens
    major_allergens = []
    allergen_keywords = {
        "Milk": ["milk", "dairy", "cream", "cheese", "whey", "casein", "lactose", "butter"],
        "Peanut": ["peanut", "groundnut"],
        "Tree Nut": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut"],
        "Egg": ["egg", "albumin"],
        "Soy": ["soy", "soya", "tofu", "soybean", "soy lecithin"],
        "Wheat/Gluten": ["wheat", "gluten", "maida", "atta", "semolina", "durum", "spelt", "barley", "rye", "wheat flour", "wheat starch"],
        "Fish": ["fish", "salmon", "tuna", "cod"],
        "Shellfish": ["shrimp", "prawn", "crab", "lobster"],
        "Sesame": ["sesame", "til", "tahini"],
        "Mustard": ["mustard"],
        "Sulfites": ["sulfite", "sulphite", "sulfur dioxide"]
    }
    
    ing_text = " ".join(i.lower() for i in ingredients)
    for allergen, keywords in allergen_keywords.items():
        for kw in keywords:
            if kw in ing_text:
                major_allergens.append(allergen)
                break
    
    # Detect contaminants
    contaminants = []
    contaminant_keywords = ["4-mei", "acrylamide", "furans", "pahs", "dioxins", "pesticide", "heavy metal"]
    for kw in contaminant_keywords:
        if kw in ing_text:
            contaminants.append(kw)
    
    # Check user-specific risks
    user_specific_risk = False
    user_allergies = [a.lower().strip() for a in user_profile.get("allergies", [])]
    user_conditions = [c.lower().strip() for c in user_profile.get("conditions", [])]
    
    for allergen in major_allergens:
        for ua in user_allergies:
            if ua in allergen.lower() or allergen.lower() in ua:
                user_specific_risk = True
                break
    
    # Calculate concern score
    concern_score = calculate_concern_score_v2(
        banned_count=len(banned_ingredients),
        restricted_count=len(restricted_ingredients),
        warning_count=len(warning_ingredients),
        high_toxicity=len(contaminants) > 0,
        is_contaminant=len(contaminants) > 0,
        is_major_allergen=len(major_allergens) > 0,
        user_specific_risk=user_specific_risk
    )
    
    # Sort ingredients by priority
    priority_order = {
        "Banned": 0,
        "Restricted": 1,
        "Warning Required": 2,
        "High Concern": 3,
        "Moderate Concern": 4,
        "Permitted": 5,
        "Information Only": 6
    }
    
    sorted_cards = sorted(ingredient_cards, key=lambda c: priority_order.get(c["regulatory_status"], 99))
    
    # Build country-wise regulatory comparison
    all_countries = set()
    for card in ingredient_cards:
        for c in card.get("country_wise_regulatory", []):
            all_countries.add(c["country"])
    
    country_comparison = {}
    for country in sorted(all_countries):
        country_comparison[country] = []
        for card in ingredient_cards:
            for c in card.get("country_wise_regulatory", []):
                if c["country"] == country:
                    country_comparison[country].append({
                        "ingredient": card["name"],
                        "status": c["status"]
                    })
    
    # Build summary
    total_ingredients = len(ingredient_cards)
    safe_count = len(permitted_ingredients) + len(info_only_ingredients)
    
    summary = {
        "total_ingredients": total_ingredients,
        "safe_ingredients": safe_count,
        "restricted_ingredients": len(restricted_ingredients),
        "banned_ingredients": len(banned_ingredients),
        "warning_ingredients": len(warning_ingredients),
        "concern_score": concern_score
    }
    
    # Build final report
    report = {
        "product_summary": {
            "total_ingredients": total_ingredients,
            "safe_ingredients": safe_count,
            "restricted_count": len(restricted_ingredients),
            "banned_count": len(banned_ingredients),
            "warning_count": len(warning_ingredients),
            "major_allergens": major_allergens,
            "contaminants": contaminants
        },
        "concern_score": concern_score,
        "banned_ingredients": [
            {
                "name": c["name"],
                "reason": f"Not authorized as a food additive in: {', '.join(c['banned_countries'][:5])}",
                "affected_countries": c["banned_countries"],
                "purpose": c["purpose"],
                "regulation": c["official_regulations"],
                "reference": c["official_references"]
            }
            for c in banned_ingredients
        ],
        "restricted_ingredients": [
            {
                "name": c["name"],
                "restriction": f"Usage restricted in: {', '.join(c['restricted_countries'][:3])}",
                "countries": c["restricted_countries"] + c["not_approved_countries"],
                "maximum_limit": c["max_permitted_limits"],
                "purpose": c["purpose"],
                "regulation": c["official_regulations"],
                "reference": c["official_references"]
            }
            for c in restricted_ingredients
        ],
        "mandatory_warning_ingredients": [
            {
                "name": c["name"],
                "warning": f"Warning label required in: {', '.join(c['warning_required_countries'][:3])}",
                "countries": c["warning_required_countries"],
                "purpose": c["purpose"],
                "regulation": c["official_regulations"],
                "reference": c["official_references"]
            }
            for c in warning_ingredients
        ],
        "ingredient_analysis": sorted_cards,
        "personalized_health_warnings": _generate_personalized_warnings_v2(
            ingredient_cards, user_profile, major_allergens
        ),
        "country_wise_regulatory_comparison": country_comparison,
        "health_risk_summary": _generate_health_risk_summary(
            concern_score, banned_ingredients, restricted_ingredients,
            warning_ingredients, major_allergens, contaminants
        )
    }
    
    return report


def _generate_personalized_warnings_v2(
    ingredient_cards: List[Dict],
    user_profile: Dict,
    major_allergens: List[str]
) -> List[Dict]:
    """Generate personalized health warnings based on user profile."""
    warnings = []
    
    if not user_profile:
        return warnings
    
    user_allergies = [a.lower().strip() for a in user_profile.get("allergies", [])]
    user_conditions = [c.lower().strip() for c in user_profile.get("conditions", [])]
    user_diet = user_profile.get("diet", "").lower().strip()
    
    # Check for allergen matches
    for allergen in major_allergens:
        for ua in user_allergies:
            if ua in allergen.lower() or allergen.lower() in ua:
                warnings.append({
                    "type": "red",
                    "title": f"⚠ Contains {allergen} — Matches Your Allergy",
                    "description": f"This product contains {allergen}, which matches your declared allergy. Avoid consumption."
                })
    
    # Check for banned ingredients
    for card in ingredient_cards:
        if card["regulatory_status"] == "Banned":
            warnings.append({
                "type": "red",
                "title": f"Contains Banned Ingredient: {card['name']}",
                "description": f"{card['name']} is banned in {', '.join(card['banned_countries'][:3])}. " +
                               f"Purpose: {card['purpose']}"
            })
    
    # Check for restricted ingredients
    for card in ingredient_cards:
        if card["regulatory_status"] == "Restricted":
            warnings.append({
                "type": "orange",
                "title": f"Restricted Ingredient: {card['name']}",
                "description": f"{card['name']} is restricted in {', '.join(card['restricted_countries'][:2])}. " +
                               f"Maximum limits apply."
            })
    
    # Check for warning-label ingredients
    for card in ingredient_cards:
        if card["regulatory_status"] == "Warning Required":
            warnings.append({
                "type": "orange",
                "title": f"Warning Label Required: {card['name']}",
                "description": f"{card['name']} requires warning labels in {', '.join(card['warning_required_countries'][:2])}."
            })
    
    # Diet-based warnings
    non_veg_keywords = ["gelatin", "gelatine", "lard", "tallow", "cochineal", "carmine", "rennet"]
    animal_keywords = non_veg_keywords + ["milk", "whey", "casein", "lactose", "honey", "egg", "albumin"]
    
    ing_text = " ".join(c["name"].lower() for c in ingredient_cards)
    
    if user_diet == "vegetarian":
        for kw in non_veg_keywords:
            if kw in ing_text:
                warnings.append({
                    "type": "red",
                    "title": "Not Suitable for Vegetarians",
                    "description": f"Contains '{kw}' — an animal-derived ingredient."
                })
                break
    
    if user_diet == "vegan":
        for kw in animal_keywords:
            if kw in ing_text:
                warnings.append({
                    "type": "red",
                    "title": "Not Suitable for Vegans",
                    "description": f"Contains '{kw}' — an animal-derived ingredient."
                })
                break
    
    return warnings


def _generate_health_risk_summary(
    concern_score: Dict,
    banned: List,
    restricted: List,
    warning: List,
    allergens: List[str],
    contaminants: List[str]
) -> Dict:
    """Generate a comprehensive health risk summary."""
    score = concern_score["score"]
    level = concern_score["level"]
    
    if score <= 20:
        overall_assessment = "This product appears to be very safe based on ingredient analysis."
    elif score <= 40:
        overall_assessment = "This product has a low level of concern. Most ingredients are widely permitted."
    elif score <= 60:
        overall_assessment = "This product has a moderate level of concern. Some ingredients may have restrictions."
    elif score <= 80:
        overall_assessment = "This product has a high level of concern. Several ingredients are restricted or require warnings."
    else:
        overall_assessment = "This product has a very high level of concern. Contains banned or high-risk ingredients."
    
    risks = []
    if banned:
        risks.append(f"Contains {len(banned)} banned ingredient(s)")
    if restricted:
        risks.append(f"Contains {len(restricted)} restricted ingredient(s)")
    if warning:
        risks.append(f"Contains {len(warning)} ingredient(s) requiring warning labels")
    if allergens:
        risks.append(f"Contains potential allergens: {', '.join(allergens)}")
    if contaminants:
        risks.append(f"May contain contaminants: {', '.join(contaminants)}")
    
    return {
        "overall_assessment": overall_assessment,
        "concern_score": score,
        "concern_level": level,
        "identified_risks": risks,
        "recommendation": _get_recommendation(score, banned, allergens)
    }


def _get_recommendation(score: int, banned: List, allergens: List[str]) -> str:
    """Generate a recommendation based on risk assessment."""
    if banned:
        return "Not recommended. Contains ingredients banned in multiple countries."
    if score >= 70:
        return "Caution advised. Consider alternatives with fewer restricted ingredients."
    if score >= 40:
        return "Moderate concern. Check ingredient details and consume in moderation."
    if allergens:
        return "Check for personal allergen matches before consumption."
    return "Generally safe for most consumers. Always check the full ingredient list."


def run_comprehensive_analysis(
    barcode: str,
    product_data: Dict,
    user_profile: Optional[Dict] = None
) -> Dict:
    """
    Run the comprehensive ingredient analysis pipeline.
    
    Args:
        barcode: Product barcode
        product_data: Normalized product data from lookup
        user_profile: Optional user health profile
    
    Returns:
        Complete analysis report
    """
    if user_profile is None:
        user_profile = {}
    
    # Build merged ingredient list
    merged_records = merge_ingredients_and_additives(product_data)
    ingredients = [r["ingredient_name"] for r in merged_records]
    
    # Run comprehensive analysis
    report = analyze_ingredients_comprehensive(ingredients, user_profile)
    
    # Add product info
    report["barcode"] = barcode
    report["product_name"] = product_data.get("name", "Unknown Product")
    report["product_brand"] = product_data.get("brand", "Unknown Brand")
    report["product_image"] = product_data.get("image_url", "")
    report["product_categories"] = product_data.get("categories", [])
    report["product_source"] = product_data.get("source", "OpenFoodFacts")
    report["ingredient_metadata"] = merged_records
    
    return report