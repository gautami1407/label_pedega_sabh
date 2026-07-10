import feedparser
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import requests
from datetime import datetime, timedelta
import re

FALLBACK_IMAGE = "https://images.unsplash.com/photo-1606787366850-de6330128bfc?w=800&q=80"

SAFETY_KEYWORDS = [
    "recall", "recalled",
    "contamination", "contaminated",
    "banned", "unsafe",
    "warning", "alert",
    "fssai", "fda",
    "mislabel", "mislabeling",
    "mislabelled",
    "health risk",
    "bacteria",
    "salmonella",
    "listeria",
    "food poisoning",
    "violation",
    "failed test",
    "quality test"
]

FOOD_CONTEXT_KEYWORDS = [
    "food", "noodles", "chocolate", "milk", "biscuit",
    "snack", "drink", "beverage", "product", "brand",
    "pack", "fssai", "fda", "factory", "consumer", "ingredient"
]

TRUSTED_SOURCES = {
    "fda", "fssai", "efsa", "usda", "fsis",
    "foodsafetynews", "reuters", "associated press", "ap news",
    "the hindu", "times of india", "hindustan times", "indian express",
    "ndtv", "bbc", "who", "cdc", "economic times", "the print", "mint", "news18"
}

FOOD_PRODUCT_REQUIRED = [
    "food", "ingredient", "label", "packaged", "product", "brand", "consumer"
]


def is_product_specific(entry, product_name):
    text = ""
    if hasattr(entry, "title"):
        text += entry.title.lower()
    if hasattr(entry, "summary"):
        text += entry.summary.lower()

    product_name = product_name.lower().strip()
    if product_name not in text:
        return False
    if not any(keyword in text for keyword in SAFETY_KEYWORDS):
        return False
    if not any(keyword in text for keyword in FOOD_CONTEXT_KEYWORDS):
        return False
    return True

def _normalize_text(value):
    return re.sub(r"\s+", " ", (value or "").strip().lower())

def _is_trusted_source(source_name):
    source_norm = _normalize_text(source_name)
    return any(src in source_norm for src in TRUSTED_SOURCES)

def _is_food_product_related(entry, product_name=None):
    text = _normalize_text(getattr(entry, "title", "") + " " + getattr(entry, "summary", ""))
    has_safety_signal = any(k in text for k in SAFETY_KEYWORDS)
    has_food_signal = any(k in text for k in FOOD_CONTEXT_KEYWORDS)
    has_product_context = any(k in text for k in FOOD_PRODUCT_REQUIRED)
    if not (has_safety_signal and has_food_signal and has_product_context):
        return False

    if product_name and product_name.strip():
        product_terms = [t for t in _normalize_text(product_name).split() if len(t) > 2]
        # Require at least one product token to reduce false positives
        if product_terms and not any(term in text for term in product_terms):
            return False
    return True


def parse_article_date(entry):
    try:
        if entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
    except:
        pass
    return None


def is_recent(entry, days=90):
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


def extract_image_from_article(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]
        twitter = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter and twitter.get("content"):
            return twitter["content"]
    except:
        pass
    return None


def resolve_image(entry, link):
    img = extract_thumbnail(entry)
    if img and img.startswith("http"):
        return img
    img = extract_image_from_article(link)
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
    return date.strftime("%b %d, %Y")


class NewsService:

    def fetch_news(self, product_name=None, max_articles=6):
        if product_name and product_name.strip():
            query = (
                f'"{product_name}" '
                '("recall" OR "contamination" OR "banned" OR "unsafe" OR '
                '"warning" OR "FSSAI" OR "FDA" OR "mislabel" OR "health risk" OR "food poisoning")'
            )
        else:
            general_terms = ["food safety recall", "FSSAI warning", "food contamination India", "food health alert"]
            query = " OR ".join([f'"{k}"' for k in general_terms])

        rss_url = (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        )

        feed = feedparser.parse(rss_url)
        articles = []
        seen = set()
        use_strict = bool(product_name and product_name.strip())

        for entry in feed.entries:
            if len(articles) >= max_articles:
                break

            link = getattr(entry, 'link', '')
            if link in seen:
                continue

            if not is_recent(entry):
                continue

            # Strict filter only when product_name is provided
            if use_strict and not is_product_specific(entry, product_name):
                continue

            parts = entry.title.split(" - ")
            source = parts[-1] if len(parts) > 1 else "News"
            title = " - ".join(parts[:-1]) if len(parts) > 1 else entry.title

            if not _is_trusted_source(source):
                continue
            if not _is_food_product_related(entry, product_name if use_strict else None):
                continue

            date_obj = parse_article_date(entry)
            articles.append({
                "title": title.strip(),
                "link": link.strip(),
                "source": source.strip(),
                "thumbnail": resolve_image(entry, link),
                "date": format_date(date_obj),
                "badge": _classify_badge(entry.title if hasattr(entry, 'title') else "")
            })
            seen.add(link)

        # Fallback: if strict search returns 0 results, try broader search without strict filter
        if use_strict and len(articles) == 0:
            broader_url = (
                "https://news.google.com/rss/search?"
                f"q={quote_plus(product_name + ' food safety health')}&hl=en-IN&gl=IN&ceid=IN:en"
            )
            feed2 = feedparser.parse(broader_url)
            for entry in feed2.entries:
                if len(articles) >= max_articles:
                    break
                link = getattr(entry, 'link', '')
                if link in seen:
                    continue
                parts = entry.title.split(" - ")
                source = parts[-1] if len(parts) > 1 else "News"
                title = " - ".join(parts[:-1]) if len(parts) > 1 else entry.title
                if not _is_food_product_related(entry, None):
                    continue
                date_obj = parse_article_date(entry)
                articles.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "source": source.strip(),
                    "thumbnail": resolve_image(entry, link),
                    "date": format_date(date_obj),
                    "badge": _classify_badge(entry.title if hasattr(entry, 'title') else "")
                })
                seen.add(link)

        # Final fallback: trusted general food safety feed
        if len(articles) == 0:
            general_url = (
                "https://news.google.com/rss/search?"
                f"q={quote_plus('food product recall FDA FSSAI EFSA warning')}&hl=en-IN&gl=IN&ceid=IN:en"
            )
            feed3 = feedparser.parse(general_url)
            for entry in feed3.entries:
                if len(articles) >= max_articles:
                    break
                link = getattr(entry, 'link', '')
                if link in seen:
                    continue
                if not is_recent(entry):
                    continue
                parts = entry.title.split(" - ")
                source = parts[-1] if len(parts) > 1 else "News"
                title = " - ".join(parts[:-1]) if len(parts) > 1 else entry.title
                if not _is_trusted_source(source):
                    continue
                if not _is_food_product_related(entry, None):
                    continue
                date_obj = parse_article_date(entry)
                articles.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "source": source.strip(),
                    "thumbnail": resolve_image(entry, link),
                    "date": format_date(date_obj),
                    "badge": _classify_badge(entry.title if hasattr(entry, 'title') else "")
                })
                seen.add(link)

        return articles


def _classify_badge(title):
    t = title.lower()
    if "recall" in t:
        return "Recall"
    if "regulation" in t or "fda" in t or "fssai" in t:
        return "Regulation"
    if "health" in t or "alert" in t or "warning" in t:
        return "Health Alert"
    return "Alert"
