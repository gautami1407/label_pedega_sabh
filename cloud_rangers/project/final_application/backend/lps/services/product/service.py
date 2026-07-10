"""

Product analysis service — wraps the legacy Analyzer engine with resolver and orchestrator.

"""

from __future__ import annotations



import logging

from functools import lru_cache



from analyzer import Analyzer

from csv_loader import RegulatoryCSVDatabase

from lps.core.config import get_settings

from lps.services.ai.orchestrator import AIOrchestrator

from lps.services.product.resolver import ProductResolver

from lps.shared.language import MEDICAL_DISCLAIMER, attention_label_from_score, attention_level_from_score

from news_service import NewsService



logger = logging.getLogger(__name__)





@lru_cache

def get_analyzer() -> Analyzer:

    return Analyzer()





@lru_cache

def get_regulatory_db() -> RegulatoryCSVDatabase:

    settings = get_settings()

    return RegulatoryCSVDatabase(csv_path=settings.regulatory_csv_path)





@lru_cache

def get_news_service() -> NewsService:

    return NewsService()





class ProductService:

    def __init__(self) -> None:

        self.analyzer = get_analyzer()

        self.reg_db = get_regulatory_db()

        self.news = get_news_service()

        self.resolver = ProductResolver()

        self.orchestrator = AIOrchestrator()



    def _enrich_response(self, result: dict, *, barcode: str | None = None) -> dict:

        if "error" in result:

            return result

        result.setdefault("disclaimer", MEDICAL_DISCLAIMER)

        insights = result.get("dashboard_insights") or result

        score = insights.get("concern_score", 0)

        result["attention_level"] = attention_level_from_score(score)

        result["attention_label"] = attention_label_from_score(score)



        if barcode:

            report = self.orchestrator.build_report(barcode, result)

            result["intelligence"] = report.model_dump()



        return result



    def analyze_barcode(self, barcode: str, preferences: dict | None = None) -> dict:

        resolved = self.resolver.resolve(barcode)

        if not resolved.get("found"):

            return {"error": resolved.get("message", "Product not found in databases")}



        result = self.analyzer.analyze_barcode(barcode, preferences or {})

        if "error" in result:

            return result



        result["resolver_source"] = resolved.get("source")

        result["resolver_confidence"] = resolved.get("product", {}).get("confidence", "medium")

        return self._enrich_response(result, barcode=barcode)



    def analyze_image(self, image_bytes: bytes, preferences: dict | None = None) -> dict:

        result = self.analyzer.analyze_image(image_bytes, preferences or {})

        if "error" in result:

            return result



        ocr_confidence = result.get("ocr_confidence")

        if ocr_confidence is None:

            ingredients = result.get("ingredients", "")

            if ingredients and ingredients.lower() not in ("not available", ""):

                result["ocr_confidence"] = 0.85

            else:

                result["ocr_confidence"] = 0.45



        if result.get("ocr_confidence", 1) < 0.6:

            result["ocr_warning"] = (

                "Label text could not be read with high confidence. "

                "Please retake the photo with better lighting and focus."

            )



        barcode = result.get("barcode") or "ocr-scan"

        return self._enrich_response(result, barcode=barcode)



    def search_products(self, query: str, page_size: int = 5) -> list:

        return self.analyzer.fetcher.search_by_name(query, page_size=page_size)



    def lookup_additive(self, identifier: str) -> dict | None:

        records = self.reg_db.lookup_additive(identifier)

        if not records:

            return None

        return {

            "additive": records[0]["name"],

            "e_number": records[0]["e_number"],

            "records": records,

        }



    def chat(self, message: str, context: dict | None = None) -> dict:

        response = self.analyzer.chat_with_assistant(message, context)

        return {"response": response, "disclaimer": MEDICAL_DISCLAIMER}



    def fetch_news(self, product_name: str | None = None) -> list:

        return self.news.fetch_news(product_name)


