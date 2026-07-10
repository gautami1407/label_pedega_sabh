import streamlit as st
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import requests
from datetime import datetime, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

FALLBACK_IMAGE = "https://images.unsplash.com/photo-1606787366850-de6330128bfc?w=800&q=80"


# ============================================================
# SAFETY KEYWORDS FILTER
# ============================================================

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
    "food",
    "noodles",
    "chocolate",
    "milk",
    "biscuit",
    "snack",
    "drink",
    "beverage",
    "product",
    "brand",
    "pack",
    "fssai",
    "fda",
    "factory",
    "consumer",
    "ingredient"
]


# ============================================================
# STRICT PRODUCT SAFETY FILTER
# ============================================================

def is_product_specific(entry, product_name):

    text = ""

    if hasattr(entry, "title"):
        text += entry.title.lower()

    if hasattr(entry, "summary"):
        text += entry.summary.lower()

    product_name = product_name.lower().strip()

    # Must contain exact product name
    if product_name not in text:
        return False

    # Must contain safety keyword
    if not any(keyword in text for keyword in SAFETY_KEYWORDS):
        return False

    # Must contain food context keyword
    if not any(keyword in text for keyword in FOOD_CONTEXT_KEYWORDS):
        return False

    return True



# ============================================================
# DATE PARSER
# ============================================================

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


# ============================================================
# THUMBNAIL FROM RSS
# ============================================================

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


# ============================================================
# SCRAPE IMAGE FROM ARTICLE PAGE
# ============================================================

@st.cache_data(ttl=3600)
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


# ============================================================
# IMAGE RESOLVER
# ============================================================

def resolve_image(entry, link):

    img = extract_thumbnail(entry)

    if img and img.startswith("http"):
        return img

    img = extract_image_from_article(link)

    if img and img.startswith("http"):
        return img

    return FALLBACK_IMAGE


# ============================================================
# FETCH PRODUCT SAFETY NEWS
# ============================================================

def fetch_product_news(product_name, max_articles=10):

    query = f'intitle:"{product_name}" ("recall" OR "contamination" OR "banned" OR "unsafe" OR "warning" OR "FSSAI" OR "FDA" OR "mislabel" OR "health risk")'

    rss_url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    )

    feed = feedparser.parse(rss_url)

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


# ============================================================
# DATE FORMATTER
# ============================================================

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


# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(
    page_title="AI Food Label Risk Intelligence",
    page_icon="🧪",
    layout="wide"
)


# CSS
st.markdown("""
<style>

.news-card {
    display:flex;
    gap:16px;
    padding:16px;
    margin-bottom:16px;
    border-radius:12px;
    border:1px solid rgba(0,0,0,0.1);
}

.news-card:hover {
    background:rgba(0,0,0,0.05);
}

.news-image {
    width:280px;
    height:160px;
    object-fit:cover;
    border-radius:10px;
}

.news-title {
    font-size:18px;
    font-weight:600;
}

.news-meta {
    font-size:13px;
    color:gray;
    margin-bottom:6px;
}

</style>
""", unsafe_allow_html=True)


st.title("🧪 AI Food Label Risk Intelligence")

product_name = st.text_input(
    "Enter product name",
    placeholder="Maggi, Kinder Joy, Amul..."
)


if st.button("🔍 Scan Product"):

    if not product_name.strip():

        st.warning("Enter product name")

    else:

        with st.spinner("Searching safety alerts..."):

            articles = fetch_product_news(product_name)

        if not articles:

            st.warning("No safety alerts found")

        else:

            st.success(f"{len(articles)} safety alert(s) found")

            for article in articles:

                img = article.get("thumbnail") or FALLBACK_IMAGE
                title = article.get("title", "")
                source = article.get("source", "")
                link = article.get("link", "")
                date = format_date(article.get("date"))

                card_html = (
                    f'<a href="{link}" target="_blank" style="text-decoration:none;color:inherit;">'
                    f'<div class="news-card">'
                    f'<img src="{img}" class="news-image" onerror="this.src=\'{FALLBACK_IMAGE}\'">'
                    f'<div>'
                    f'<div class="news-meta">{source} • {date}</div>'
                    f'<div class="news-title">{title}</div>'
                    f'</div>'
                    f'</div>'
                    f'</a>'
                    
                )

                st.markdown(card_html, unsafe_allow_html=True)
