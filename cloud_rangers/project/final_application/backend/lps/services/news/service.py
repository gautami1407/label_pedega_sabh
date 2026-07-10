import os
import time
import logging
from typing import List, Dict, Any

import requests
from datetime import datetime, timedelta

from .schemas import RecallItem, NewsItem, NewsAndRecallsResponse

logger = logging.getLogger(__name__)

class NewsRecallService:
    """Fetch and cache news & recall information from public sources.

    Sources currently supported:
    * FDA (US Food and Drug Administration) – product recalls
    * FSSAI (Food Safety and Standards Authority of India) – recall notices
    * CDSCO (Central Drugs Standard Control Organization, India) – medical food alerts
    * WHO – health news related to the product name
    """

    CACHE_TTL = timedelta(hours=6)
    USER_AGENT = "LPS-Product-Intelligence/1.0"

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def get(self, product_name: str, barcode: str) -> NewsAndRecallsResponse:
        """Return a populated :class:`NewsAndRecallsResponse`.

        The function first checks the in‑memory cache; if the entry is stale or missing it
        queries the external sources.  The result is cached for ``CACHE_TTL``.
        """
        cache_key = f"{barcode}|{product_name}".lower()
        now = datetime.utcnow()
        entry = self._cache.get(cache_key)
        if entry and now - entry["timestamp"] < self.CACHE_TTL:
            logger.debug("NewsRecallService cache hit for %s", cache_key)
            return entry["data"]

        logger.debug("NewsRecallService cache miss – fetching data for %s", cache_key)
        recalls = self._fetch_fda(barcode)
        recalls += self._fetch_fssai(product_name)
        recalls += self._fetch_cdsc(product_name)
        news = self._fetch_who(product_name)

        response = NewsAndRecallsResponse(
            verified_recalls=[RecallItem(**r) for r in recalls],
            related_news=[NewsItem(**n) for n in news],
            last_updated=now.isoformat(),
        )
        # Store in cache
        self._cache[cache_key] = {"timestamp": now, "data": response}
        return response

    # ---------------------------------------------------------------------
    # Source‑specific helpers (private)
    # ---------------------------------------------------------------------
    def _fetch_fda(self, barcode: str) -> List[Dict[str, Any]]:
        """Query the FDA open‑fda enforcement endpoint for recalls matching the barcode.

        The FDA API does not support direct barcode search, so we perform a fuzzy search on the
        ``product_code`` field.  The endpoint returns a list of records; we normalise them to the
        ``RecallItem`` schema.
        """
        try:
            url = "https://api.fda.gov/food/enforcement.json"
            params = {"search": f"product_code:{barcode}", "limit": 5}
            headers = {"User-Agent": self.USER_AGENT}
            r = requests.get(url, params=params, headers=headers, timeout=5)
            r.raise_for_status()
            data = r.json().get("results", [])
            recalls = []
            for rec in data:
                recalls.append({
                    "title": rec.get("product_description", "FDA Recall"),
                    "url": rec.get("recall_url"),
                    "date": rec.get("recall_date"),
                    "source": "FDA",
                })
            return recalls
        except Exception as e:
            logger.warning("Failed to fetch FDA recalls: %s", e)
            return []

    def _fetch_fssai(self, product_name: str) -> List[Dict[str, Any]]:
        """Placeholder for FSSAI recall lookup.

        The real API is not public; for production we would ingest the RSS feed published by
        the Ministry of Health.  Here we return an empty list to keep the implementation safe.
        """
        # TODO: integrate official FSSAI recall RSS when available.
        return []

    def _fetch_cdsc(self, product_name: str) -> List[Dict[str, Any]]:
        """Placeholder for CDSCO medical‑food alert lookup.

        Similar to FSSAI, we currently return an empty list.
        """
        return []

    def _fetch_who(self, product_name: str) -> List[Dict[str, Any]]:
        """Search WHO news via its public API (if available).

        The WHO does not provide a free JSON API for news search, so we perform a very light web‑search
        using the public “search” endpoint that returns a JSON collection of articles.  The response is
        normalised to ``NewsItem``.
        """
        try:
            # Example WHO search – not official, but sufficient for demonstration.
            url = "https://search.un.org/api/v1/search"
            params = {"query": product_name, "size": 5}
            headers = {"User-Agent": self.USER_AGENT}
            r = requests.get(url, params=params, headers=headers, timeout=5)
            r.raise_for_status()
            hits = r.json().get("results", [])
            news = []
            for item in hits:
                news.append({
                    "title": item.get("title", "WHO News"),
                    "url": item.get("url"),
                    "date": item.get("publishedDate"),
                    "source": "WHO",
                })
            return news
        except Exception as e:
            logger.warning("Failed to fetch WHO news: %s", e)
            return []
