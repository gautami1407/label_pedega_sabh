import pandas as pd
import os

def load_banned_ingredients(filepath):
    """
    Loads the banned ingredients CSV into a pandas DataFrame.
    """
    try:
        return pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Banned ingredients file not found at {filepath}")
        return pd.DataFrame()

def check_banned_ingredients(ingredients_list, banned_df):
    """
    Checks if any ingredient in the list is present in the banned ingredients DataFrame.
    Returns a list of dictionaries with details about the banned ingredients found.
    """
    found_risks = []
    
    if banned_df.empty:
        return found_risks

    # Convert banned ingredients to lower case for comparison
    banned_df['Ingredient_Lower'] = banned_df['Ingredient'].str.lower()
    
    for ingredient in ingredients_list:
        # Check for exact matches first
        match = banned_df[banned_df['Ingredient_Lower'] == ingredient]
        
        # If no exact match, try partial match (e.g. "red 40" in "red 40 lake")
        if match.empty:
             match = banned_df[banned_df['Ingredient_Lower'].apply(lambda x: x in ingredient)]

        if not match.empty:
            for _, row in match.iterrows():
                found_risks.append({
                    "ingredient": row['Ingredient'],
                    "risk_level": row['Risk Level'],
                    "details": row['Details'],
                    "banned_in": row['Banned In'],
                    "found_as": ingredient
                })

    return found_risks

def calculate_health_score(nutriments):
    """
    Calculates a simple health score based on nutrients.
    Scale: 0 (Unhealthy) to 100 (Healthy).
    This is a simplified version of Nutri-Score.
    """
    score = 70 # Start with a base score
    
    if not nutriments:
        return None

    # Penalties
    score -= nutriments.get('sugars_100g', 0) * 1
    score -= nutriments.get('saturated-fat_100g', 0) * 2
    score -= nutriments.get('salt_100g', 0) * 10
    
    # Bonuses
    score += nutriments.get('fiber_100g', 0) * 2
    score += nutriments.get('proteins_100g', 0) * 1
    
    # Clamp score between 0 and 100
    return max(0, min(100, score))
