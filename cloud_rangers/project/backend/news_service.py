# news_service.py
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import requests
from datetime import datetime, timedelta

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
    "food","noodles","chocolate","milk","biscuit","snack","drink",
    "beverage","product","brand","pack","fssai","fda","factory",
    "consumer","ingredient"
]

# -----------------------------
# Helper functions
# -----------------------------
def is_product_specific(entry, product_name):
    text = ""
    if hasattr(entry, "title"):
        text += entry.title.lower()
    if hasattr(entry, "summary"):
        text += entry.summary.lower()

    product_name = product_name.lower().strip()
    # check if any word from product_name is in text
    if not any(word in text for word in product_name.split()):
        return False

    # keep safety keywords check
    if not any(keyword in text for keyword in SAFETY_KEYWORDS):
        return False

    # make FOOD_CONTEXT_KEYWORDS optional
    # if you want to catch more articles, comment this line:
    # if not any(keyword in text for keyword in FOOD_CONTEXT_KEYWORDS):
    #     return False

    return True


def parse_article_date(entry):
    try:
        if entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
    except:
        pass
    return None

def is_recent(entry, days=30):
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

# -----------------------------
# Main function to fetch news
# -----------------------------
def fetch_product_news(product_name, max_articles=10):
    """
    Fetch news articles related to a product's safety from Google News RSS.
    
    Args:
        product_name (str): Name of the product to search for.
        max_articles (int): Maximum number of articles to return.

    Returns:
        list[dict]: List of article dictionaries with title, link, source, thumbnail, and date.
    """

    # -----------------------------
    # Prepare RSS query
    # -----------------------------
    query = f'{product_name} recall OR contamination OR banned OR unsafe OR warning OR FSSAI OR FDA OR mislabel OR "health risk"'
    rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"

    # -----------------------------
    # Parse RSS feed
    # -----------------------------
    feed = feedparser.parse(rss_url)
    print(f"RSS entries fetched: {len(feed.entries)}")
    for entry in feed.entries[:5]:  # show first 5 for quick debug
        print("Title:", entry.title)

    # -----------------------------
    # Process entries
    # -----------------------------
    articles = []
    seen = set()

    for entry in feed.entries:
        link = entry.link
        if link in seen:
            continue
        if not is_recent(entry):
            continue
        if not is_product_specific(entry, product_name):
            continue

        # Extract source from title if present
        parts = entry.title.split(" - ")
        source = parts[-1] if len(parts) > 1 else "News"
        title = " - ".join(parts[:-1]) if len(parts) > 1 else entry.title

        article = {
            "title": title.strip(),
            "link": link.strip(),
            "source": source.strip(),
            "thumbnail": resolve_image(entry, link),
            "date": parse_article_date(entry)
        }

        articles.append(article)
        seen.add(link)

        if len(articles) >= max_articles:
            break

    return articles


def get_safety_news(product_name, max_articles=10):
    articles = fetch_product_news(product_name, max_articles)
    formatted = []
    for a in articles:
        formatted.append({
            "title": a.get("title"),
            "link": a.get("link"),
            "source": a.get("source"),
            "thumbnail": a.get("thumbnail") or FALLBACK_IMAGE,
            "date": format_date(a.get("date"))
        })
    return formatted
