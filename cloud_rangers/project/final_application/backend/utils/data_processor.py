def normalize_product_data(api_data):
    """
    Standardizes the API response into a common internal format.
    """
    if not api_data:
        return None

    return {
        "name": api_data.get("name", "Unknown Product"),
        "brand": api_data.get("brand", "Unknown Brand"),
        "image_url": api_data.get("image_url", ""),
        "ingredients_text": api_data.get("ingredients_text", ""),
        "nutriments": api_data.get("nutriments", {}),
        "categories": api_data.get("categories", "").split(','),
        "nova_group": api_data.get("nova_group"),
        "nutriscore_grade": api_data.get("nutriscore_grade"),
        "source": api_data.get("source", "Unknown")
    }

def parse_ingredients(ingredients_text):
    """
    Parses the ingredients text into a list of individual ingredients.
    This is a simple implementation and can be improved with regex or NLP.
    """
    if not ingredients_text:
        return []

    # Basic splitting by comma, stripping whitespace, and lowercasing
    ingredients = [ing.strip().lower() for ing in ingredients_text.split(',')]
    
    # Remove empty strings
    return [ing for ing in ingredients if ing]
