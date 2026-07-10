"""
Liability-safe language constants for Label Padegha Sabh.

All user-facing warnings must use these templates.
Never use: Danger, Critical, Unsafe, Dangerous, Do not consume.
"""

MEDICAL_DISCLAIMER = (
    "This information is for educational purposes only and is not medical advice. "
    "Always read the physical product label and consult a qualified healthcare "
    "professional for personal dietary or health decisions."
)

# Maps legacy/internal severity to user-facing attention levels
ATTENTION_LEVELS = {
    "low": "Low Attention",
    "moderate": "Moderate Attention",
    "high": "High Attention",
}

WARNING_TEMPLATES = {
    "allergen_profile_match": {
        "type": "high",
        "title": "Allergen Match — Worth Your Attention",
        "description": (
            "This product contains {allergen}, which matches an allergen listed in "
            "your health profile. You may wish to review the ingredient list carefully."
        ),
    },
    "allergen_present": {
        "type": "moderate",
        "title": "Allergen Present — {allergen}",
        "description": (
            "This product lists {allergen} as an ingredient. "
            "Check whether this is relevant to your dietary needs."
        ),
    },
    "regulatory_restriction": {
        "type": "high",
        "title": "Regulatory Attention — {ingredient}",
        "description": (
            "{ingredient} has restricted or prohibited status in {jurisdictions} "
            "according to our regulatory database. {reason}"
        ),
    },
    "diet_mismatch": {
        "type": "high",
        "title": "Dietary Preference Note",
        "description": (
            "This product may contain ingredients that are not aligned with your "
            "{diet} dietary preference."
        ),
    },
    "sugar_attention": {
        "type": "high",
        "title": "Sugar Content — Worth Your Attention",
        "description": (
            "This product has elevated sugar content, which may be worth noting "
            "given your dietary preferences."
        ),
    },
}

# Terms that must never appear in user-facing output
FORBIDDEN_TERMS = [
    "danger",
    "critical",
    "unsafe",
    "dangerous",
    "do not consume",
    "toxic",
    "poison",
    "deadly",
    "lethal",
]


def sanitize_warning_text(text: str) -> str:
    """Replace forbidden liability-risk terms in warning copy."""
    if not text:
        return text
    result = text
    replacements = {
        "DANGER:": "Note:",
        "DANGER": "Attention",
        "CRITICAL ALLERGEN:": "Allergen Match:",
        "CRITICAL ALLERGEN": "Allergen Match",
        "CRITICAL:": "High Attention:",
        "CRITICAL": "High Attention",
        "Banned:": "Regulatory Attention:",
        "Banned in": "Restricted in",
        "unsafe": "worth your attention",
        "Unsafe": "Worth Your Attention",
        "dangerous": "worth noting",
        "Dangerous": "Worth Noting",
    }
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def attention_level_from_score(score: int) -> str:
    """Map internal numeric score to attention level tier."""
    if score >= 67:
        return "high"
    if score >= 34:
        return "moderate"
    return "low"


def attention_label_from_score(score: int) -> str:
    """Return user-facing attention level label."""
    return ATTENTION_LEVELS[attention_level_from_score(score)]
