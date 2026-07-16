# news_service.py — Enhanced v3
# Smarter news fetching with brand/product/ingredient awareness

import feedparser
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import requests
from datetime import datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)

FALLBACK_IMAGE = "https://images.unsplash.com/photo-1606787366850-de6330128bfc?w=800&q=80"

SAFETY_KEYWORDS = [
    "recall", "recalled", "contamination", "contaminated",
    "banned", "unsafe", "warning", "alert", "fssai", "fda", "efsa",
    "mislabel", "mislabeling", "health risk", "bacteria",
    "salmonella", "listeria", "food poisoning", "violation",
    "failed test", "quality test", "unhealthy", "dangerous",
    "adulterated", "substandard", "penalty", "fine", "seized",
    "harmful", "cancer", "carcinogen", "toxic", "lead",
    "pesticide", "heavy metal", "e. coli", "ecoli", "withdrawn",
    "prohibited", "restricted", "limit", "regulation", "compliance",
    "investigation", "outbreak", "sick", "hospital", "death",
    "allergen", "undeclared", "packaging defect", "foreign matter"
]

FOOD_CONTEXT_KEYWORDS = [
    "food", "noodles", "chocolate", "milk", "biscuit", "snack",
    "drink", "beverage", "product", "brand", "pack", "fssai",
    "fda", "factory", "consumer", "ingredient", "nutrition",
    "calories", "sugar", "salt", "fat", "health", "diet",
    "processed", "additive", "preservative", "colour", "flavor",
    "label", "packaging", "manufacturer", "company", "market"
]

EXCLUDE_KEYWORDS = [
    "jewelry", "real estate", "travel", "sports", "entertainment",
    "movie", "music", "concert", "hotel", "vacation", "tourism",
    "stock market", "cricket", "football", "politics", "election",
    "hide and seek", "hidden", "gemstone", "diamond", "gold price"
]

# Known brand/manufacturer mappings for better search
BRAND_ALIASES = {
    "maggi": ["nestle", "maggi noodles", "maggi masala"],
    "coca-cola": ["coca cola", "coke", "cocacola"],
    "pepsi": ["pepsico", "pepsi cola"],
    "cadbury": ["mondelez", "cadbury india", "cadbury dairy milk"],
    "oreo": ["mondelez", "nabisco", "oreo biscuit"],
    "kitkat": ["nestle", "kit kat", "kitkat chocolate"],
    "pringles": ["kellanova", "kellogg", "pringles chips"],
    "lays": ["pepsico", "lay's", "frito-lay", "lays chips"],
    "red bull": ["redbull", "red bull energy"],
    "kinder": ["ferrero", "kinder joy", "kinder chocolate"],
    "amul": ["gujarat cooperative", "amul butter", "amul milk"],
    "britannia": ["britannia industries", "britannia biscuit"],
    "horlicks": ["gsk", "glaxosmithkline", "horlicks health"],
    "bournvita": ["mondelez", "cadbury bournvita"],
    "parle": ["parle products", "parle g", "parle biscuit"],
    "heinz": ["kraft heinz", "heinz ketchup"],
    "kellogg": ["kellogg's", "kellanova", "corn flakes"],
    "knorr": ["unilever", "knorr soup", "knorr seasoning"],
    "m&m": ["mars", "m&m's", "mars chocolate"],
    "domino": ["domino's", "domino pizza", "jubilant foodworks"],
}

def _get_brand_terms(product_name, brand_name=""):
    """Generate multiple search terms from brand + product name."""
    terms = set()
    product_lower = product_name.lower().strip()
    brand_lower = brand_name.lower().strip()
    
    # Add brand aliases if known
    for key, aliases in BRAND_ALIASES.items():
        if key in product_lower or key in brand_lower:
            for alias in aliases:
                terms.add(alias)
    
    # Add the product name itself
    terms.add(product_lower)
    
    # Add individual words (3+ chars)
    for word in product_lower.split():
        if len(word) >= 3 and word not in ['the', 'and', 'for', 'with']:
            terms.add(word)
    
    # Add brand name
    if brand_lower:
        terms.add(brand_lower)
        for word in brand_lower.split():
            if len(word) >= 3:
                terms.add(word)
    
    return list(terms)

# ── Ingredient extraction for better news queries ─────────────────────
def extract_ingredient_keywords(ingredients):
    """Extract key ingredients/searches from ingredient list for targeted news."""
    keywords = []
    if not ingredients:
        return keywords
    
    ingredients_str = " ".join(ingredients).lower()
    
    # Common additive names and their news search terms
    additive_news_map = {
        "titanium dioxide": ["titanium dioxide food safety", "e171 ban"],
        "e150d": ["caramel colour safety", "e150d regulations"],
        "e102": ["tartrazine safety", "yellow 5 food dye"],
        "e110": ["sunset yellow safety", "yellow 6 food dye"],
        "e129": ["allura red safety", "red 40 food dye"],
        "e133": ["brilliant blue safety", "blue 1 food dye"],
        "sodium benzoate": ["sodium benzoate health", "benzoate preservative"],
        "bha": ["bha preservative safety"],
        "bht": ["bht preservative safety"],
        "tbhq": ["tbhq safety", "tertiary butylhydroquinone"],
        "aspartame": ["aspartame safety", "aspartame artificial sweetener"],
        "sucralose": ["sucralose safety", "splenda sweetener"],
        "potassium bromate": ["potassium bromate ban", "bromate bread safety"],
    }
    
    for key, search_terms in additive_news_map.items():
        if key in ingredients_str:
            keywords.extend(search_terms)
    
    return list(set(keywords))

def is_relevant_article(entry, product_name, brand_name=""):
    """Check if article is relevant to the product with better filtering."""
    text = ""
    if hasattr(entry, "title"):
        text += entry.title.lower() + " "
    if hasattr(entry, "summary"):
        text += entry.summary.lower()
    
    # Check for exclusion keywords first
    if any(excl in text for excl in EXCLUDE_KEYWORDS):
        return False
    
    product_name = product_name.lower().strip()
    search_terms = _get_brand_terms(product_name, brand_name)
    
    # Must mention at least one search term
    if not any(term in text for term in search_terms):
        return False
    
    # Must mention either a safety keyword OR food context keyword
    all_relevant = SAFETY_KEYWORDS + FOOD_CONTEXT_KEYWORDS
    return any(keyword in text for keyword in all_relevant)

def parse_article_date(entry):
    try:
        if entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
    except:
        pass
    return None

def is_recent(entry, days=365):
    date = parse_article_date(entry)
    if not date:
        return True
    return date >= datetime.now() - timedelta(days=days)

def extract_thumbnail(entry):
    try:
        if hasattr(entry, "media_content"):
            return entry.media_content[0]["url"]
    except:
        pass
    try:
        if hasattr(entry, "media_thumbnail"):
            return entry.media_thumbnail[0]["url"]
    except:
        pass
    try:
        if hasattr(entry, "summary"):
            soup = BeautifulSoup(entry.summary, "html.parser")
            img = soup.find("img")
            if img:
                return img.get("src")
    except:
        pass
    return None

def resolve_image(entry, link):
    img = extract_thumbnail(entry)
    if img and img.startswith("http"):
        return img
    return FALLBACK_IMAGE

def format_date(date):
    if not date:
        return "Recently"
    diff = datetime.now() - date
    if diff.days == 0:
        return "Today"
    if diff.days == 1:
        return "Yesterday"
    if diff.days < 7:
        return f"{diff.days} days ago"
    if diff.days < 30:
        return f"{diff.days // 7} weeks ago"
    if diff.days < 365:
        return f"{diff.days // 30} months ago"
    return date.strftime("%b %d, %Y")


def get_safety_news(product_name, brand_name="", max_articles=10, ingredients=None, category=None):
    """
    Fetch intelligent safety news for a product.
    Uses brand-aware search with multiple query strategies.
    Now also considers ingredients and category for targeted news.
    """
    articles = []
    seen = set()
    
    search_terms = _get_brand_terms(product_name, brand_name)
    
    # Build queries based on multiple factors
    queries = [
        f"{product_name} recall OR contamination OR banned OR unsafe",
        f"{product_name} food safety OR health warning",
    ]
    
    # Add ingredient-specific queries if provided
    if ingredients:
        ingredient_keywords = extract_ingredient_keywords(ingredients)
        for kw in ingredient_keywords[:3]:  # Limit to avoid too many queries
            queries.insert(1, f"{kw} safety OR regulation")
    
    # Add category-specific queries if provided
    if category:
        cat_terms = category.split(",")[0].strip() if "," in category else category
        queries.append(f"{cat_terms} food safety OR regulatory update")
    
    # Add brand-specific query
    if brand_name:
        queries.insert(0, f"{brand_name} {product_name} recall OR safety")
    
    # Categorize articles
    for query in queries:
        if len(articles) >= max_articles:
            break
            
        rss_url = (
            f"https://news.google.com/rss/search?q={quote_plus(query)}"
            f"&hl=en-IN&gl=IN&ceid=IN:en"
        )
        
        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            logger.warning(f"RSS parse error for '{query[:30]}': {e}")
            continue
        
        for entry in feed.entries:
            if len(articles) >= max_articles:
                break
                
            link = entry.link
            if link in seen:
                continue
            if not is_recent(entry):
                continue
            if not is_relevant_article(entry, product_name, brand_name):
                continue
            
            seen.add(link)
            
            # Extract source from title
            parts = entry.title.split(" - ")
            source = parts[-1] if len(parts) > 1 else "News"
            title = " - ".join(parts[:-1]) if len(parts) > 1 else entry.title
            
            # Determine category
            entry_text = (entry.title + " " + entry.summary).lower()
            category = 'news'
            if 'recall' in entry_text:
                category = 'recall'
            elif 'banned' in entry_text or 'prohibited' in entry_text:
                category = 'regulation'
            elif 'study' in entry_text or 'research' in entry_text:
                category = 'study'
            
            articles.append({
                "title": title.strip(),
                "link": link.strip(),
                "source": source.strip(),
                "thumbnail": resolve_image(entry, link),
                "date": format_date(parse_article_date(entry)),
                "category": category
            })
    
    return articles