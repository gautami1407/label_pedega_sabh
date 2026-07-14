"""
Gemini Integration — uses google-genai (new SDK, not deprecated google-generativeai)
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_api_key

class GeminiHandler:
    def __init__(self):
        self.api_key = get_api_key("gemini")
        if not self.api_key or "your_gemini" in self.api_key:
            raise ValueError("Gemini API key not configured.")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _generate(self, prompt: str) -> str:
        client = self._get_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text.strip()

    def explain_risks(self, product_name, ingredients, risks):
        prompt = f"""You are a food safety expert. Analyze this product for a consumer.

Product: {product_name}
Ingredients: {', '.join(ingredients)}
Identified Risks: {risks}

1. Explain WHY these ingredients are flagged.
2. Assess overall healthiness.
3. Give a clear recommendation: Avoid / Consume in Moderation / Generally Safe.

Be concise, factual, and consumer-friendly. Use plain English."""
        try:
            return self._generate(prompt)
        except Exception as e:
            return f"AI analysis unavailable: {str(e)}"

    def start_chat(self, product_context):
        self._product_context = product_context

    def send_message(self, message: str) -> str:
        context = getattr(self, '_product_context', {})
        prompt = f"""You are a food safety assistant. Use this product context to answer.

Product: {context.get('name', 'Unknown')} by {context.get('brand', 'Unknown')}
Ingredients: {', '.join(context.get('ingredients', [])[:10])}
Concern Score: {context.get('concern_score', 'N/A')}/100
Allergens: {', '.join(context.get('allergens', []))}

User question: {message}

Answer factually and concisely."""
        try:
            return self._generate(prompt)
        except Exception as e:
            return f"AI response unavailable: {str(e)}"

    def analyze_label_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        from google import genai
        from google.genai import types
        client = self._get_client()
        prompt = """Extract product information from this food label image.
Return ONLY valid JSON with these fields:
{
  "name": "product name",
  "brand": "brand name",
  "ingredients_text": "full ingredients list as text",
  "nutriments": {
    "energy-kcal_100g": number,
    "fat_100g": number,
    "saturated-fat_100g": number,
    "carbohydrates_100g": number,
    "sugars_100g": number,
    "fiber_100g": number,
    "proteins_100g": number,
    "salt_100g": number
  },
  "categories": "product category",
  "nova_group": null,
  "nutriscore_grade": null,
  "source": "Gemini OCR"
}"""
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
            )
            return response.text.strip()
        except Exception as e:
            return f'{{"error": "OCR failed: {str(e)}"}}'
