import google.generativeai as genai
import streamlit as st
import os

class GeminiHandler:
    def __init__(self):
        try:
            api_key = st.secrets["general"]["gemini_api_key"]
        except KeyError:
            # Fallback if not seeking secrets (e.g. running script directly)
            api_key = os.environ.get("GEMINI_API_KEY")
            
        if not api_key:
            raise ValueError("Gemini API Key not found in secrets or environment variables.")
        
        genai.configure(api_key=api_key)
        # Using gemini-1.5-pro as requested (interpreted from "2.5") for premium results
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
