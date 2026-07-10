import google.generativeai as genai
import os
try:
    from ..config import get_api_key
except ImportError:
    # If running where backend is in sys.path
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import get_api_key

class GeminiHandler:
    def __init__(self):
        api_key = get_api_key("gemini")
            
        if not api_key:
            raise ValueError("Gemini API Key not found in secrets or environment variables.")
        
        genai.configure(api_key=api_key)
        # Using gemini-1.5-pro as requested
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.chat_session = None

    def explain_risks(self, product_name, ingredients, risks):
        """
        Generates a user-friendly explanation of identified risks using Gemini.
        """
        prompt = f"""
        You are an expert food safety analyst. Analyze the following product for a consumer.
        
        Product: {product_name}
        Ingredients: {', '.join(ingredients)}
        
        Identified Potential Risks (from our database):
        {risks}
        
        Task:
        1. Explain WHY these specific ingredients are flagged.
        2. Assess the overall healthiness of the product.
        3. Provide a clear recommendation (e.g., "Avoid", "Consume in Moderation", "Safe").
        
        Format the output with Markdown, using bolding and bullet points for readability. Be concise but informative.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating explanation: {str(e)}"

    def start_chat(self, product_context):
        """
        Initializes a chat session with context about the product.
        """
        history = [
            {"role": "user", "parts": [f"I am looking at a product called {product_context['name']}. Here are the details: {product_context}"]},
            {"role": "model", "parts": ["Okay, I understand. I am ready to answer questions about this product."]}
        ]
        self.chat_session = self.model.start_chat(history=history)

    def send_message(self, message):
        """
        Sends a message to the chat session and returns the response.
        """
        if not self.chat_session:
             return "Chat session not initialized. Please scan a product first."
            
        try:
            response = self.chat_session.send_message(message)
            return response.text
        except Exception as e:
            return f"Error sending message: {str(e)}"

    def analyze_label_image(self, image_bytes: bytes, mime_type: str) -> str:
        """
        Performs OCR and extracts product name, brand, ingredients, and nutrients.
        """
        prompt = """
        Analyze this product label image. Perform OCR and extract:
        1. Product Name
        2. Brand (if visible, otherwise "Unknown")
        3. Raw ingredients text (list of ingredients as they appear on the label)
        4. Nutrition facts (if visible, extract calories/energy, sugar, salt/sodium, saturated fat, protein, fiber per 100g or per serving)
        
        Return a JSON object exactly matching this schema:
        {
          "name": "Product Name",
          "brand": "Brand Name",
          "ingredients_text": "ingredient1, ingredient2, ingredient3...",
          "nutriments": {
            "energy_100g": 123.0,
            "sugars_100g": 5.0,
            "saturated-fat_100g": 1.2,
            "salt_100g": 0.5,
            "proteins_100g": 2.0,
            "fiber_100g": 0.8
          }
        }
        Only output the raw JSON. Do not include markdown code block formatting (like ```json).
        """
        try:
            response = self.model.generate_content([
                prompt,
                {"mime_type": mime_type, "data": image_bytes}
            ])
            return response.text
        except Exception as e:
            raise ValueError(f"Gemini API error during image analysis: {str(e)}")

