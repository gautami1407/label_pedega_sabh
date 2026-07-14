"""
data_processor.py
=================
Utilities for normalising product data and building the final merged
ingredient list from all sources (ingredients_text + additives_tags +
ingredients_tags + traces_tags + ingredient_analysis).
"""
import re

def normalize_product_data(api_data):
    """Standardize any source's product dict into the common internal format."""
    if not api_data:
        return None

    cats_raw = api_data.get("categories", "")
    if isinstance(cats_raw, list):
        categories = [c.strip() for c in cats_raw if c.strip()]
    else:
        categories = [c.strip() for c in str(cats_raw).split(',') if c.strip()]

    return {
        "name":                api_data.get("name", "Unknown Product"),
        "brand":               api_data.get("brand", "Unknown Brand"),
        "image_url":           api_data.get("image_url", ""),
        "ingredients_text":    api_data.get("ingredients_text", ""),
        "nutriments":          api_data.get("nutriments", {}),
        "categories":          categories,
        "nova_group":          api_data.get("nova_group"),
        "nutriscore_grade":    api_data.get("nutriscore_grade"),
        "allergens":           api_data.get("allergens", []),
        # Legacy field
        "additives":           api_data.get("additives", []),
        # Expanded additive / ingredient fields
        "additives_tags":      api_data.get("additives_tags", []),
        "additives_original":  api_data.get("additives_original", []),
        "additives_n":         api_data.get("additives_n", 0),
        "ingredients_tags":    api_data.get("ingredients_tags", []),
        "traces_tags":         api_data.get("traces_tags", []),
        "ingredient_analysis": api_data.get("ingredient_analysis", []),
        "attribute_groups":    api_data.get("attribute_groups", []),
        "countries":           api_data.get("countries", ""),
        "labels":              api_data.get("labels", ""),
        "packaging":           api_data.get("packaging", ""),
        "source":              api_data.get("source", "Unknown"),
        # CSV-enriched fields (passed through unchanged)
        "health_note":         api_data.get("health_note", ""),
        "health_concern":      api_data.get("health_concern", ""),
        "consumer_note":       api_data.get("consumer_note", ""),
        "key_differences":     api_data.get("key_differences", ""),
        "regulatory_raw":      api_data.get("regulatory_raw", {}),
    }


def parse_ingredients(ingredients_text):
    """
    Parse an ingredients string into a clean list.
    Handles nested parentheses like 'emulsifier (soy lecithin)' by
    flattening the top-level items and also extracting sub-items.
    """
    if not ingredients_text:
        return []

    # Remove HTML entities and tags
    text = re.sub(r'<[^>]+>', '', ingredients_text)
    text = text.replace('&amp;', '&').replace('&#39;', "'")

    # Split on commas that are NOT inside parentheses
    items = []
    depth = 0
    current = []
    for ch in text:
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            items.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        items.append(''.join(current).strip())

    cleaned = []
    for item in items:
        # Strip leading percentages, asterisks, and numbers
        item = re.sub(r'^[\d\.\*\%\s]+', '', item).strip()
        # Remove content in square brackets
        item = re.sub(r'\[.*?\]', '', item).strip()
        # Lowercase, remove trailing punctuation
        item = item.lower().rstrip('.')
        if item and len(item) > 1:
            cleaned.append(item)

    return cleaned


# ══════════════════════════════════════════════════════════════════
# E-NUMBER / INS-NUMBER  →  CANONICAL NAME  RESOLVER
# ══════════════════════════════════════════════════════════════════
# Keys are the lowercase code as it appears in additives_tags after
# stripping the "en:" prefix, e.g. "e102", "ins102".
# Each entry carries: canonical_name, ins_number, e_number.
# ──────────────────────────────────────────────────────────────────

_ADDITIVE_CODE_MAP = {
    # ── Colours ───────────────────────────────────────────────────
    "e100":  {"name": "Curcumin",             "ins": "INS100",  "e": "E100"},
    "e101":  {"name": "Riboflavin",           "ins": "INS101",  "e": "E101"},
    "e102":  {"name": "Tartrazine",           "ins": "INS102",  "e": "E102"},
    "e104":  {"name": "Quinoline Yellow",     "ins": "INS104",  "e": "E104"},
    "e110":  {"name": "Sunset Yellow FCF",    "ins": "INS110",  "e": "E110"},
    "e120":  {"name": "Carmine",              "ins": "INS120",  "e": "E120"},
    "e122":  {"name": "Carmoisine",           "ins": "INS122",  "e": "E122"},
    "e123":  {"name": "Amaranth",             "ins": "INS123",  "e": "E123"},
    "e124":  {"name": "Ponceau 4R",           "ins": "INS124",  "e": "E124"},
    "e127":  {"name": "Erythrosine",          "ins": "INS127",  "e": "E127"},
    "e129":  {"name": "Allura Red AC",        "ins": "INS129",  "e": "E129"},
    "e131":  {"name": "Patent Blue V",        "ins": "INS131",  "e": "E131"},
    "e132":  {"name": "Indigotine",           "ins": "INS132",  "e": "E132"},
    "e133":  {"name": "Brilliant Blue FCF",   "ins": "INS133",  "e": "E133"},
    "e140":  {"name": "Chlorophylls",         "ins": "INS140",  "e": "E140"},
    "e141":  {"name": "Copper Chlorophyll",   "ins": "INS141",  "e": "E141"},
    "e150a": {"name": "Caramel (plain)",      "ins": "INS150a", "e": "E150a"},
    "e150b": {"name": "Caramel (caustic sulfite)", "ins": "INS150b", "e": "E150b"},
    "e150c": {"name": "Caramel (ammonia)",    "ins": "INS150c", "e": "E150c"},
    "e150d": {"name": "Caramel Colour IV",    "ins": "INS150d", "e": "E150d"},
    "e151":  {"name": "Brilliant Black BN",   "ins": "INS151",  "e": "E151"},
    "e160a": {"name": "Beta Carotene",        "ins": "INS160a", "e": "E160a"},
    "e160b": {"name": "Annatto",              "ins": "INS160b", "e": "E160b"},
    "e161b": {"name": "Lutein",               "ins": "INS161b", "e": "E161b"},
    "e162":  {"name": "Beetroot Red",         "ins": "INS162",  "e": "E162"},
    "e163":  {"name": "Anthocyanins",         "ins": "INS163",  "e": "E163"},
    "e171":  {"name": "Titanium Dioxide",     "ins": "INS171",  "e": "E171"},
    "e172":  {"name": "Iron Oxides",          "ins": "INS172",  "e": "E172"},
    # ── Preservatives ─────────────────────────────────────────────
    "e200":  {"name": "Sorbic Acid",          "ins": "INS200",  "e": "E200"},
    "e202":  {"name": "Potassium Sorbate",    "ins": "INS202",  "e": "E202"},
    "e210":  {"name": "Benzoic Acid",         "ins": "INS210",  "e": "E210"},
    "e211":  {"name": "Sodium Benzoate",      "ins": "INS211",  "e": "E211"},
    "e212":  {"name": "Potassium Benzoate",   "ins": "INS212",  "e": "E212"},
    "e213":  {"name": "Calcium Benzoate",     "ins": "INS213",  "e": "E213"},
    "e220":  {"name": "Sulphur Dioxide",      "ins": "INS220",  "e": "E220"},
    "e221":  {"name": "Sodium Sulphite",      "ins": "INS221",  "e": "E221"},
    "e222":  {"name": "Sodium Bisulphite",    "ins": "INS222",  "e": "E222"},
    "e223":  {"name": "Sodium Metabisulphite","ins": "INS223",  "e": "E223"},
    "e224":  {"name": "Potassium Metabisulphite","ins":"INS224","e": "E224"},
    "e249":  {"name": "Potassium Nitrite",    "ins": "INS249",  "e": "E249"},
    "e250":  {"name": "Sodium Nitrite",       "ins": "INS250",  "e": "E250"},
    "e251":  {"name": "Sodium Nitrate",       "ins": "INS251",  "e": "E251"},
    "e252":  {"name": "Potassium Nitrate",    "ins": "INS252",  "e": "E252"},
    "e280":  {"name": "Propionic Acid",       "ins": "INS280",  "e": "E280"},
    "e281":  {"name": "Sodium Propionate",    "ins": "INS281",  "e": "E281"},
    "e282":  {"name": "Calcium Propionate",   "ins": "INS282",  "e": "E282"},
    "e283":  {"name": "Potassium Propionate", "ins": "INS283",  "e": "E283"},
    # ── Antioxidants ──────────────────────────────────────────────
    "e300":  {"name": "Ascorbic Acid",        "ins": "INS300",  "e": "E300"},
    "e301":  {"name": "Sodium Ascorbate",     "ins": "INS301",  "e": "E301"},
    "e306":  {"name": "Tocopherols",          "ins": "INS306",  "e": "E306"},
    "e307":  {"name": "Alpha-Tocopherol",     "ins": "INS307",  "e": "E307"},
    "e310":  {"name": "Propyl Gallate",       "ins": "INS310",  "e": "E310"},
    "e319":  {"name": "TBHQ",                 "ins": "INS319",  "e": "E319"},
    "e320":  {"name": "BHA",                  "ins": "INS320",  "e": "E320"},
    "e321":  {"name": "BHT",                  "ins": "INS321",  "e": "E321"},
    # ── Acidity regulators / Acids ────────────────────────────────
    "e330":  {"name": "Citric Acid",          "ins": "INS330",  "e": "E330"},
    "e331":  {"name": "Sodium Citrates",      "ins": "INS331",  "e": "E331"},
    "e332":  {"name": "Potassium Citrates",   "ins": "INS332",  "e": "E332"},
    "e333":  {"name": "Calcium Citrates",     "ins": "INS333",  "e": "E333"},
    "e338":  {"name": "Phosphoric Acid",      "ins": "INS338",  "e": "E338"},
    "e339":  {"name": "Sodium Phosphates",    "ins": "INS339",  "e": "E339"},
    "e340":  {"name": "Potassium Phosphates", "ins": "INS340",  "e": "E340"},
    "e341":  {"name": "Calcium Phosphates",   "ins": "INS341",  "e": "E341"},
    "e350":  {"name": "Sodium Malate",        "ins": "INS350",  "e": "E350"},
    "e363":  {"name": "Succinic Acid",        "ins": "INS363",  "e": "E363"},
    "e380":  {"name": "Triammonium Citrate",  "ins": "INS380",  "e": "E380"},
    # ── Thickeners / Stabilisers / Emulsifiers ───────────────────
    "e400":  {"name": "Alginic Acid",         "ins": "INS400",  "e": "E400"},
    "e401":  {"name": "Sodium Alginate",      "ins": "INS401",  "e": "E401"},
    "e402":  {"name": "Potassium Alginate",   "ins": "INS402",  "e": "E402"},
    "e404":  {"name": "Calcium Alginate",     "ins": "INS404",  "e": "E404"},
    "e406":  {"name": "Agar",                 "ins": "INS406",  "e": "E406"},
    "e407":  {"name": "Carrageenan",          "ins": "INS407",  "e": "E407"},
    "e410":  {"name": "Locust Bean Gum",      "ins": "INS410",  "e": "E410"},
    "e412":  {"name": "Guar Gum",             "ins": "INS412",  "e": "E412"},
    "e413":  {"name": "Tragacanth",           "ins": "INS413",  "e": "E413"},
    "e414":  {"name": "Gum Arabic",           "ins": "INS414",  "e": "E414"},
    "e415":  {"name": "Xanthan Gum",          "ins": "INS415",  "e": "E415"},
    "e416":  {"name": "Karaya Gum",           "ins": "INS416",  "e": "E416"},
    "e417":  {"name": "Tara Gum",             "ins": "INS417",  "e": "E417"},
    "e418":  {"name": "Gellan Gum",           "ins": "INS418",  "e": "E418"},
    "e420":  {"name": "Sorbitol",             "ins": "INS420",  "e": "E420"},
    "e421":  {"name": "Mannitol",             "ins": "INS421",  "e": "E421"},
    "e422":  {"name": "Glycerol",             "ins": "INS422",  "e": "E422"},
    "e440":  {"name": "Pectin",               "ins": "INS440",  "e": "E440"},
    "e442":  {"name": "Ammonium Phosphatides","ins": "INS442",  "e": "E442"},
    "e450":  {"name": "Diphosphates",         "ins": "INS450",  "e": "E450"},
    "e451":  {"name": "Triphosphates",        "ins": "INS451",  "e": "E451"},
    "e452":  {"name": "Polyphosphates",       "ins": "INS452",  "e": "E452"},
    "e460":  {"name": "Cellulose",            "ins": "INS460",  "e": "E460"},
    "e461":  {"name": "Methyl Cellulose",     "ins": "INS461",  "e": "E461"},
    "e466":  {"name": "Carboxymethyl Cellulose","ins":"INS466", "e": "E466"},
    "e471":  {"name": "Mono- and Diglycerides","ins":"INS471",  "e": "E471"},
    "e472a": {"name": "Acetic Acid Esters of Mono- and Diglycerides","ins":"INS472a","e":"E472a"},
    "e472b": {"name": "Lactic Acid Esters of Mono- and Diglycerides","ins":"INS472b","e":"E472b"},
    "e472e": {"name": "Diacetyl Tartaric Acid Esters (DATEM)","ins":"INS472e","e":"E472e"},
    "e473":  {"name": "Sucrose Esters of Fatty Acids","ins":"INS473","e":"E473"},
    "e476":  {"name": "PGPR",                 "ins": "INS476",  "e": "E476"},
    "e477":  {"name": "Propylene Glycol Esters","ins":"INS477", "e": "E477"},
    "e481":  {"name": "Sodium Stearoyl Lactylate","ins":"INS481","e":"E481"},
    "e482":  {"name": "Calcium Stearoyl Lactylate","ins":"INS482","e":"E482"},
    "e491":  {"name": "Sorbitan Monostearate","ins":"INS491",   "e": "E491"},
    # ── Flavour enhancers ─────────────────────────────────────────
    "e620":  {"name": "Glutamic Acid",        "ins": "INS620",  "e": "E620"},
    "e621":  {"name": "Monosodium Glutamate", "ins": "INS621",  "e": "E621"},
    "e622":  {"name": "Monopotassium Glutamate","ins":"INS622", "e": "E622"},
    "e623":  {"name": "Calcium Diglutamate",  "ins": "INS623",  "e": "E623"},
    "e627":  {"name": "Disodium Guanylate",   "ins": "INS627",  "e": "E627"},
    "e631":  {"name": "Disodium Inosinate",   "ins": "INS631",  "e": "E631"},
    "e635":  {"name": "Disodium Ribonucleotides","ins":"INS635","e": "E635"},
    # ── Sweeteners ───────────────────────────────────────────────
    "e420":  {"name": "Sorbitol",             "ins": "INS420",  "e": "E420"},
    "e950":  {"name": "Acesulfame Potassium", "ins": "INS950",  "e": "E950"},
    "e951":  {"name": "Aspartame",            "ins": "INS951",  "e": "E951"},
    "e952":  {"name": "Cyclamates",           "ins": "INS952",  "e": "E952"},
    "e953":  {"name": "Isomalt",              "ins": "INS953",  "e": "E953"},
    "e954":  {"name": "Saccharin",            "ins": "INS954",  "e": "E954"},
    "e955":  {"name": "Sucralose",            "ins": "INS955",  "e": "E955"},
    "e957":  {"name": "Thaumatin",            "ins": "INS957",  "e": "E957"},
    "e960":  {"name": "Steviol Glycosides",   "ins": "INS960",  "e": "E960"},
    "e961":  {"name": "Neotame",              "ins": "INS961",  "e": "E961"},
    "e962":  {"name": "Aspartame-Acesulfame Salt","ins":"INS962","e":"E962"},
    "e965":  {"name": "Maltitol",             "ins": "INS965",  "e": "E965"},
    "e967":  {"name": "Xylitol",              "ins": "INS967",  "e": "E967"},
    "e968":  {"name": "Erythritol",           "ins": "INS968",  "e": "E968"},
    # ── Flour treatment / Misc ────────────────────────────────────
    "e170":  {"name": "Calcium Carbonate",    "ins": "INS170",  "e": "E170"},
    "e322":  {"name": "Lecithins",            "ins": "INS322",  "e": "E322"},
    "e500":  {"name": "Sodium Carbonates",    "ins": "INS500",  "e": "E500"},
    "e501":  {"name": "Potassium Carbonates", "ins": "INS501",  "e": "E501"},
    "e503":  {"name": "Ammonium Carbonates",  "ins": "INS503",  "e": "E503"},
    "e504":  {"name": "Magnesium Carbonates", "ins": "INS504",  "e": "E504"},
    "e508":  {"name": "Potassium Chloride",   "ins": "INS508",  "e": "E508"},
    "e509":  {"name": "Calcium Chloride",     "ins": "INS509",  "e": "E509"},
    "e516":  {"name": "Calcium Sulphate",     "ins": "INS516",  "e": "E516"},
    "e524":  {"name": "Sodium Hydroxide",     "ins": "INS524",  "e": "E524"},
    "e551":  {"name": "Silicon Dioxide",      "ins": "INS551",  "e": "E551"},
    "e570":  {"name": "Fatty Acids",          "ins": "INS570",  "e": "E570"},
    "e901":  {"name": "Beeswax",              "ins": "INS901",  "e": "E901"},
    "e903":  {"name": "Carnauba Wax",         "ins": "INS903",  "e": "E903"},
    "e904":  {"name": "Shellac",              "ins": "INS904",  "e": "E904"},
    "e924a": {"name": "Potassium Bromate",    "ins": "INS924a", "e": "E924a"},
    "e927b": {"name": "Carbamide",            "ins": "INS927b", "e": "E927b"},
    "e928":  {"name": "Benzoyl Peroxide",     "ins": "INS928",  "e": "E928"},
    "e930":  {"name": "Calcium Peroxide",     "ins": "INS930",  "e": "E930"},
}

# Build a reverse lookup: also accept "ins102", "ins 102", "e 102" etc.
def _build_alias_map(code_map):
    alias = {}
    for k, v in code_map.items():
        # canonical key already lowercase e.g. "e102"
        alias[k] = v
        # strip spaces: "e 102" → "e102"
        alias[k.replace(" ", "")] = v
        # ins variant: "ins102"
        ins_key = k.replace("e", "ins", 1) if k.startswith("e") else k
        alias[ins_key] = v
        alias[ins_key.replace(" ", "")] = v
    return alias

_ALIAS_MAP = _build_alias_map(_ADDITIVE_CODE_MAP)


# ══════════════════════════════════════════════════════════════════
# PUBLIC RESOLVER
# ══════════════════════════════════════════════════════════════════

def resolve_additive_code(raw_code):
    """
    Convert an E-number or INS-number string to a structured dict.

    Input examples:  "e102", "E102", "ins102", "INS 102", "en:e102"
    Returns:
        {
          "ingredient_name": "Tartrazine",
          "original_label":  "E102",
          "source":          "additives",
          "ins_number":      "INS102",
          "e_number":        "E102",
          "confidence":      "high"   # found in map
        }
    or None if not recognised.
    """
    if not raw_code:
        return None

    cleaned = str(raw_code).strip().lower()
    # Strip OpenFoodFacts "en:" prefix
    if cleaned.startswith("en:"):
        cleaned = cleaned[3:]
    # Remove spaces
    cleaned = cleaned.replace(" ", "")

    entry = _ALIAS_MAP.get(cleaned)
    if not entry:
        return None

    return {
        "ingredient_name": entry["name"],
        "original_label":  raw_code.strip(),
        "source":          "additives",
        "ins_number":      entry["ins"],
        "e_number":        entry["e"],
        "confidence":      "high",
    }


# ══════════════════════════════════════════════════════════════════
# MAIN MERGE FUNCTION
# ══════════════════════════════════════════════════════════════════

def merge_ingredients_and_additives(product):
    """
    Build the final unified ingredient list from ALL OFF fields.

    Priority / sources consulted (in order):
      1. ingredients_text     → parse_ingredients()
      2. ingredients_tags     → already-clean strings from OFF
      3. additives_tags       → resolve E/INS codes → canonical names
      4. additives_original   → legacy additives list
      5. ingredient_analysis  → objects with 'id' / 'text' fields

    Deduplication:
      - Normalise every name to lowercase+stripped key.
      - INS/E synonyms collapse to the canonical name (e.g. "e102",
        "ins102", and "tartrazine" all map to "Tartrazine").
      - If the same additive appears in multiple sources, its record's
        'source' field is updated to "both".

    Returns a list of metadata dicts:
      {
        "ingredient_name": str,   # display name
        "original_label":  str,   # as it appeared in the source field
        "source":          str,   # "ingredients" | "additives" | "both"
        "ins_number":      str,   # e.g. "INS102"  or ""
        "e_number":        str,   # e.g. "E102"    or ""
        "confidence":      str,   # "high" | "medium"
      }
    """
    # Tracks canonical_name.lower() → record index in `records`
    seen = {}
    records = []

    def _add(ingredient_name, original_label, source, ins_number, e_number, confidence):
        key = ingredient_name.strip().lower()
        if not key or len(key) < 2:
            return
        if key in seen:
            # Upgrade source to "both" if different source already present
            idx = seen[key]
            existing_src = records[idx]["source"]
            if existing_src != source and existing_src != "both":
                records[idx]["source"] = "both"
        else:
            seen[key] = len(records)
            records.append({
                "ingredient_name": ingredient_name.strip(),
                "original_label":  original_label,
                "source":          source,
                "ins_number":      ins_number,
                "e_number":        e_number,
                "confidence":      confidence,
            })

    # ── Source 1: ingredients_text ────────────────────────────────
    raw_text = product.get("ingredients_text", "")
    for ing in parse_ingredients(raw_text):
        # Check if a plain-text ingredient IS actually a code e.g. "e471"
        resolved = resolve_additive_code(ing)
        if resolved:
            _add(resolved["ingredient_name"], ing, "ingredients",
                 resolved["ins_number"], resolved["e_number"], "high")
        else:
            _add(ing.title(), ing, "ingredients", "", "", "medium")

    # ── Source 2: ingredients_tags ────────────────────────────────
    for tag in (product.get("ingredients_tags") or []):
        tag = str(tag).strip()
        if not tag:
            continue
        resolved = resolve_additive_code(tag)
        if resolved:
            _add(resolved["ingredient_name"], tag, "ingredients",
                 resolved["ins_number"], resolved["e_number"], "high")
        else:
            clean = tag.replace("en:", "").replace("-", " ").strip().title()
            if len(clean) > 1:
                _add(clean, tag, "ingredients", "", "", "medium")

    # ── Source 3: additives_tags (primary additive source) ────────
    for code in (product.get("additives_tags") or []):
        resolved = resolve_additive_code(code)
        if resolved:
            _add(resolved["ingredient_name"], str(code).strip(), "additives",
                 resolved["ins_number"], resolved["e_number"], "high")
        else:
            # Unknown code — include as-is so it still gets checked
            clean = str(code).replace("en:", "").upper().strip()
            if len(clean) > 1:
                _add(clean, str(code).strip(), "additives", "", "", "medium")

    # ── Source 4: additives_original (legacy field) ───────────────
    for item in (product.get("additives_original") or []):
        resolved = resolve_additive_code(item)
        if resolved:
            _add(resolved["ingredient_name"], str(item).strip(), "additives",
                 resolved["ins_number"], resolved["e_number"], "high")
        else:
            clean = str(item).strip()
            if len(clean) > 1:
                _add(clean.title(), clean, "additives", "", "", "medium")

    # ── Source 5: ingredient_analysis objects ─────────────────────
    for obj in (product.get("ingredient_analysis") or []):
        if not isinstance(obj, dict):
            continue
        # OFF ingredient_analysis objects have an 'id' like "en:e471" and
        # optional 'text' field with a human-readable name
        text_val = str(obj.get("text") or obj.get("id") or "").strip()
        if not text_val:
            continue
        resolved = resolve_additive_code(text_val)
        if resolved:
            _add(resolved["ingredient_name"], text_val, "additives",
                 resolved["ins_number"], resolved["e_number"], "high")
        else:
            clean = text_val.replace("en:", "").replace("-", " ").strip().title()
            if len(clean) > 1:
                _add(clean, text_val, "ingredients", "", "", "medium")

    return records


def get_merged_ingredient_names(product):
    """
    Convenience wrapper — returns just the display name strings
    from merge_ingredients_and_additives(), suitable for passing
    directly to the analysis engine steps.
    """
    return [r["ingredient_name"] for r in merge_ingredients_and_additives(product)]
