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
        "name":             api_data.get("name", "Unknown Product"),
        "brand":            api_data.get("brand", "Unknown Brand"),
        "image_url":        api_data.get("image_url", ""),
        "ingredients_text": api_data.get("ingredients_text", ""),
        "nutriments":       api_data.get("nutriments", {}),
        "categories":       categories,
        "nova_group":       api_data.get("nova_group"),
        "nutriscore_grade": api_data.get("nutriscore_grade"),
        "allergens":        api_data.get("allergens", []),
        "additives":        api_data.get("additives", []),
        "countries":        api_data.get("countries", ""),
        "labels":           api_data.get("labels", ""),
        "packaging":        api_data.get("packaging", ""),
        "source":           api_data.get("source", "Unknown"),
        # CSV-enriched fields (passed through unchanged)
        "health_note":      api_data.get("health_note", ""),
        "health_concern":   api_data.get("health_concern", ""),
        "consumer_note":    api_data.get("consumer_note", ""),
        "key_differences":  api_data.get("key_differences", ""),
        "regulatory_raw":   api_data.get("regulatory_raw", {}),
    }


import re

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
