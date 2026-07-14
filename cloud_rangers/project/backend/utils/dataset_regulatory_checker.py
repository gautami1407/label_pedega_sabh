"""
Dataset Regulatory Checker
===========================
Checks scanned product ingredients exclusively against the uploaded
Food Additive & Contaminant Regulation Dataset (3 sheets):

  1. additive_limits.csv      — Additive_Limits sheet
  2. eu_not_authorised.csv    — EU_Not_Authorised_Additives sheet
  3. recall_incidents.csv     — Recall_Incidents sheet

Rules:
- Match by exact name first, then by substring / synonym.
- If the ingredient appears in the dataset → report every matching row.
- If it does NOT appear → status = "No Match".
- Never use external knowledge; only the three CSVs are consulted.
- Preserve wording from the dataset verbatim wherever possible.
"""

import os
import re
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# ── File paths ────────────────────────────────────────────────────────────────
_HERE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR  = os.path.join(_HERE, "data")

_ADDITIVE_LIMITS_PATH   = os.path.join(_DATA_DIR, "additive_limits.csv")
_EU_NOT_AUTH_PATH       = os.path.join(_DATA_DIR, "eu_not_authorised.csv")
_RECALL_INCIDENTS_PATH  = os.path.join(_DATA_DIR, "recall_incidents.csv")

# ── Load CSVs once at module import ───────────────────────────────────────────
def _load(path, label):
    try:
        df = pd.read_csv(path)
        logger.info(f"[DatasetChecker] Loaded {label} ({len(df)} rows)")
        return df
    except Exception as exc:
        logger.warning(f"[DatasetChecker] Could not load {label}: {exc}")
        return pd.DataFrame()

_DF_ADDITIVE   = _load(_ADDITIVE_LIMITS_PATH,  "additive_limits.csv")
_DF_EU_BANNED  = _load(_EU_NOT_AUTH_PATH,       "eu_not_authorised.csv")
_DF_RECALLS    = _load(_RECALL_INCIDENTS_PATH,  "recall_incidents.csv")


# ── Synonyms / aliases known from the dataset ────────────────────────────────
# Key   = canonical lowercase name as it appears in the dataset
# Value = additional aliases / E-numbers / abbreviations that should also match
_SYNONYMS = {
    "titanium dioxide":             ["e171", "ins 171", "ins171", "titanium white"],
    "potassium bromate":            ["e924a", "ins 924a", "ins924a"],
    "lecithins":                    ["e322", "ins 322", "soy lecithin", "sunflower lecithin", "ins322"],
    "pgpr":                         ["e476", "ins 476", "polyglycerol polyricinoleate", "ins476"],
    "citric acid":                  ["e330", "ins 330", "ins330"],
    "calcium carbonate":            ["e170", "ins 170", "ins170"],
    "caramel colour iv":            ["e150d", "ins 150d", "ins150d", "caramel color", "caramel e150d"],
    "phosphoric acid":              ["e338", "ins 338", "ins338"],
    "caffeine":                     ["1,3,7-trimethylxanthine"],
    "natural flavouring":           ["natural flavoring", "natural flavor", "natural flavours"],
    "allura red ac":                ["e129", "ins 129", "red 40", "ins129"],
    "sunset yellow fcf":            ["e110", "ins 110", "yellow 6", "ins110"],
    "tartrazine":                   ["e102", "ins 102", "yellow 5", "ins102"],
    "ponceau 4r":                   ["e124", "ins 124", "ins124"],
    "sodium benzoate":              ["e211", "ins 211", "ins211"],
    "sulphur dioxide":              ["e220", "ins 220", "sulfur dioxide", "ins220"],
    "tbhq":                         ["ins 319", "tertiary butylhydroquinone", "ins319"],
    "cyclamates":                   ["e952", "ins 952", "cyclamate", "ins952"],
    "brominated vegetable oil (bvo)":["bvo", "brominated vegetable oil"],
    "brominated vegetable oil":     ["bvo"],
    "red 3 (erythrosine)":          ["e127", "ins 127", "erythrosine", "ins127"],
    "sudan i":                      ["sudan 1", "ci solvent yellow 14"],
    "sudan ii":                     ["sudan 2"],
    "sudan iii":                    ["sudan 3"],
    "sudan iv":                     ["sudan 4"],
    "rhodamine b":                  ["rhodamine"],
    "metanil yellow":               ["metanil"],
    "sodium nitrite":               ["e250", "ins 250", "ins250"],
    "nitrates":                     ["e251", "e252", "ins 251", "ins 252", "sodium nitrate", "potassium nitrate"],
    "saccharin":                    ["e954", "ins 954"],
    "cyclamate":                    ["e952", "ins 952"],
}

# ── Normalise a string for fuzzy matching ─────────────────────────────────────
def _norm(s):
    """Lowercase, strip, collapse whitespace, remove parenthetical suffixes."""
    s = str(s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    # Remove trailing parenthetical like "(if used)" or "(not normally present in dairy milk)"
    s = re.sub(r"\s*\(.*?\)\s*$", "", s).strip()
    return s


def _aliases_for(name_lower):
    """Return the set of all aliases (including the name itself) for matching."""
    aliases = {name_lower}
    for canon, syns in _SYNONYMS.items():
        if name_lower == canon or name_lower in syns:
            aliases.add(canon)
            aliases.update(syns)
    return aliases


def _ingredient_matches_row(ingredient_norm, row_name_norm):
    """
    True if the ingredient matches the dataset row name.
    Tries: exact → ingredient contains row name → row name contains ingredient.
    """
    if ingredient_norm == row_name_norm:
        return True
    ing_aliases = _aliases_for(ingredient_norm)
    row_aliases = _aliases_for(row_name_norm)
    # Any alias of the ingredient appears as exact match against any alias of the row
    if ing_aliases & row_aliases:
        return True
    # Substring: the row's canonical name appears inside the ingredient string
    if row_name_norm in ingredient_norm:
        return True
    # Substring: the ingredient string appears inside the row's canonical name
    if ingredient_norm in row_name_norm:
        return True
    return False


# ── Determine status category from free-text status string ───────────────────
_BANNED_KEYWORDS     = ["banned", "prohibited", "not permitted", "not approved",
                         "not authorised", "revoked", "illegal", "phase-out"]
_RESTRICTED_KEYWORDS = ["restricted", "warning label", "mandatory warning",
                         "limited uses", "conditions vary", "maximum limits",
                         "category-specific", "quantum satis", "gmp",
                         "labeling rules apply", "labelling rules apply",
                         "permitted with mandatory warning", "warning label required"]


def _classify_status(status_text):
    sl = str(status_text).lower()
    for kw in _BANNED_KEYWORDS:
        if kw in sl:
            return "Banned"
    for kw in _RESTRICTED_KEYWORDS:
        if kw in sl:
            return "Restricted"
    if "permitted" in sl or "allowed" in sl:
        return "Allowed"
    return "Restricted"  # default to Restricted when unclear


# ── Sheet 1: Additive_Limits lookup ──────────────────────────────────────────
def _check_additive_limits(ingredient_norm):
    """
    Returns list of match dicts from additive_limits.csv for one ingredient.
    Each dict has keys: ingredient, ins_e_no, function, food_category,
                        jurisdiction, status_limit, status_class,
                        difference_notes, source, table_group, matched_as
    """
    results = []
    if _DF_ADDITIVE.empty:
        return results

    for _, row in _DF_ADDITIVE.iterrows():
        row_name_norm = _norm(row.get("Ingredient", ""))
        if not _ingredient_matches_row(ingredient_norm, row_name_norm):
            continue

        status_raw = str(row.get("Status_Limit", "")).strip()
        matched_as = str(row.get("Ingredient", "")).strip()

        results.append({
            "sheet":            "Additive_Limits",
            "ingredient":       matched_as,
            "matched_as":       matched_as if _norm(matched_as) != ingredient_norm else "",
            "ins_e_no":         str(row.get("INS_E_No", "—")).strip(),
            "function":         str(row.get("Function", "")).strip(),
            "food_category":    str(row.get("Food_Category", "")).strip(),
            "jurisdiction":     str(row.get("Jurisdiction", "")).strip(),
            "status_limit":     status_raw,
            "status_class":     _classify_status(status_raw),
            "difference_notes": str(row.get("Difference_Notes", "")).strip(),
            "source":           str(row.get("Source", "")).strip(),
            "table_group":      str(row.get("Table_Group", "")).strip(),
        })

    return results


# ── Sheet 2: EU_Not_Authorised lookup ─────────────────────────────────────────
def _check_eu_not_authorised(ingredient_norm):
    """
    Returns list of match dicts from eu_not_authorised.csv for one ingredient.
    """
    results = []
    if _DF_EU_BANNED.empty:
        return results

    for _, row in _DF_EU_BANNED.iterrows():
        row_name_norm = _norm(row.get("Ingredient", ""))
        if not _ingredient_matches_row(ingredient_norm, row_name_norm):
            continue

        eu_status = str(row.get("EU_Status", "")).strip()
        results.append({
            "sheet":         "EU_Not_Authorised_Additives",
            "ingredient":    str(row.get("Ingredient", "")).strip(),
            "matched_as":    str(row.get("Ingredient", "")).strip(),
            "e_number":      str(row.get("E_Number", "—")).strip(),
            "function":      str(row.get("Function", "")).strip(),
            "found_in":      str(row.get("Commonly_Found_In", "")).strip(),
            "jurisdiction":  "EU",
            "status_limit":  eu_status,
            "status_class":  _classify_status(eu_status),
            "reason":        str(row.get("Reason", "")).strip(),
        })

    return results


# ── Sheet 3: Recall_Incidents lookup ─────────────────────────────────────────
def _check_recall_incidents(ingredient_norm):
    """
    Matches ingredient against Contaminant column in recall_incidents.csv.
    A match means the contaminant name overlaps with the scanned ingredient name.
    Returns list of recall match dicts.
    """
    results = []
    if _DF_RECALLS.empty:
        return results

    for _, row in _DF_RECALLS.iterrows():
        contaminant_norm = _norm(row.get("Contaminant", ""))
        if not contaminant_norm or contaminant_norm in ("—", "-", "nan"):
            continue
        if not _ingredient_matches_row(ingredient_norm, contaminant_norm):
            continue

        brand   = str(row.get("Brand", "")).strip()
        product = str(row.get("Product_Variant", "")).strip()
        if brand in ("—", "-", "nan", ""):
            brand = "Unspecified"
        if product in ("—", "-", "nan", ""):
            product = "Unspecified"

        results.append({
            "sheet":          "Recall_Incidents",
            "brand":          brand,
            "product":        product,
            "contaminant":    str(row.get("Contaminant", "")).strip(),
            "hazard":         str(row.get("Hazard_Category", "")).strip(),
            "cause":          str(row.get("Reason_Present", "")).strip(),
            "health_concern": str(row.get("Health_Concern", "")).strip(),
            "agency":         str(row.get("Country_Agency", "")).strip(),
            "threshold":      str(row.get("Limit_or_Threshold_Cited", "")).strip(),
            "action":         str(row.get("Regulatory_Action_and_Date", "")).strip(),
            "current_status": str(row.get("Current_Status", "")).strip(),
        })

    return results


# ── Public API ────────────────────────────────────────────────────────────────
def check_ingredients_against_dataset(ingredients):
    """
    Main entry point.  Call with the list of ingredient strings extracted
    from a scanned product.

    Returns a dict:
    {
      "rows": [
        {
          "ingredient":    <original name from product label>,
          "status":        "Banned" | "Restricted" | "Allowed" | "No Match",
          "matched_name":  <name as it appears in dataset, or "">,
          "additive_hits": [ ... ],   # from additive_limits.csv
          "eu_hits":       [ ... ],   # from eu_not_authorised.csv
          "recall_hits":   [ ... ],   # from recall_incidents.csv
        },
        ...
      ],
      "summary": {
        "total":       <int>,
        "banned":      <int>,
        "restricted":  <int>,
        "allowed":     <int>,
        "no_match":    <int>,
        "jurisdictions_with_issues": [ <str>, ... ],
        "recall_brands": [ <str>, ... ],
      }
    }
    """
    rows = []
    jurisdictions_with_issues = set()
    recall_brands = set()

    for ingredient in ingredients:
        if not ingredient or not str(ingredient).strip():
            continue

        ing_norm        = _norm(ingredient)
        additive_hits   = _check_additive_limits(ing_norm)
        eu_hits         = _check_eu_not_authorised(ing_norm)
        recall_hits     = _check_recall_incidents(ing_norm)

        all_hits = additive_hits + eu_hits

        if not all_hits and not recall_hits:
            # Nothing found in any sheet
            rows.append({
                "ingredient":   ingredient,
                "status":       "No Match",
                "matched_name": "",
                "additive_hits": [],
                "eu_hits":       [],
                "recall_hits":   [],
            })
            continue

        # Determine worst status across all hits
        all_statuses = [h["status_class"] for h in all_hits]
        if "Banned" in all_statuses:
            overall = "Banned"
        elif "Restricted" in all_statuses:
            overall = "Restricted"
        elif "Allowed" in all_statuses:
            overall = "Allowed"
        elif recall_hits:
            overall = "Restricted"   # recall without explicit status → flag as Restricted
        else:
            overall = "Restricted"

        # Collect jurisdictions that have issues (non-Allowed)
        for h in all_hits:
            if h["status_class"] in ("Banned", "Restricted"):
                jur = h.get("jurisdiction", "")
                if jur:
                    jurisdictions_with_issues.add(jur)

        # Collect recall brand/product pairs
        for r in recall_hits:
            if r["brand"] not in ("Unspecified", "—"):
                recall_brands.add(r["brand"])

        # Best matched name: prefer EU sheet (most specific) then additive sheet
        matched_name = ""
        if eu_hits:
            matched_name = eu_hits[0]["ingredient"]
        elif additive_hits:
            matched_name = additive_hits[0]["ingredient"]

        rows.append({
            "ingredient":    ingredient,
            "status":        overall,
            "matched_name":  matched_name if _norm(matched_name) != ing_norm else "",
            "additive_hits": additive_hits,
            "eu_hits":       eu_hits,
            "recall_hits":   recall_hits,
        })

    # Build summary
    statuses    = [r["status"] for r in rows]
    n_banned    = statuses.count("Banned")
    n_restricted= statuses.count("Restricted")
    n_allowed   = statuses.count("Allowed")
    n_no_match  = statuses.count("No Match")

    summary = {
        "total":                   len(rows),
        "banned":                  n_banned,
        "restricted":              n_restricted,
        "allowed":                 n_allowed,
        "no_match":                n_no_match,
        "jurisdictions_with_issues": sorted(jurisdictions_with_issues),
        "recall_brands":           sorted(recall_brands),
    }

    logger.info(
        f"[DatasetChecker] Checked {len(rows)} ingredients — "
        f"Banned:{n_banned} Restricted:{n_restricted} "
        f"Allowed:{n_allowed} NoMatch:{n_no_match}"
    )

    return {"rows": rows, "summary": summary}
