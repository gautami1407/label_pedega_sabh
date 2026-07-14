# news_service.py — Enhanced v2
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


def get_safety_news(product_name, brand_name="", max_articles=10):
    """
    Fetch intelligent safety news for a product.
    Uses brand-aware search with multiple query strategies.
    """
    articles = []
    seen = set()
    
    search_terms = _get_brand_terms(product_name, brand_name)
    
    # Try multiple search queries for better coverage
    queries = [
        f"{product_name} recall OR contamination OR banned OR unsafe",
        f"{product_name} food safety OR health warning",
        f"{product_name} FDA OR FSSAI OR EFSA regulation",
    ]
    
    # Add brand-specific query
    if brand_name:
        queries.insert(0, f"{brand_name} {product_name} recall OR safety")
    
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
            
            articles.append({
                "title": title.strip(),
                "link": link.strip(),
                "source": source.strip(),
                "thumbnail": resolve_image(entry, link),
                "date": format_date(parse_article_date(entry))
            })
    
    return articles