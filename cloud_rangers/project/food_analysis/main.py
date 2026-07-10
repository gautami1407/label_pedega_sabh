import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pandas as pd
import time
from utils.barcode_scanner import decode_barcode
from utils.product_lookup import lookup_product
from utils.data_processor import normalize_product_data, parse_ingredients
from utils.risk_engine import load_banned_ingredients, check_banned_ingredients, calculate_health_score
from utils.gemini_integration import GeminiHandler

# ---------------------------
# Page Configuration
# ---------------------------
st.set_page_config(
    page_title="Food Ranger | AI Food Analyst",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------
# Custom CSS for Premium Look
# ---------------------------
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
        color: #ffffff;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-family: 'Segoe UI', sans-serif;
        color: #ffffff;
    }
    h1 {
        font-weight: 700;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
    }
    
    /* Cards */
    .css-1r6slb0, .css-1keyail {
        background-color: #383838;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        border: 1px solid #444;
    }
    
    /* Custom Risk Badges */
    .risk-badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 20px;
        font-size: 0.9em;
        font-weight: bold;
        color: white;
        margin-right: 5px;
        margin-bottom: 5px;
    }
    .risk-high { background-color: #e53935; box-shadow: 0 2px 5px rgba(229, 57, 53, 0.4); }
    .risk-medium { background-color: #fb8c00; box-shadow: 0 2px 5px rgba(251, 140, 0, 0.4); }
    .risk-low { background-color: #43a047; box-shadow: 0 2px 5px rgba(67, 160, 71, 0.4); }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #4CAF50 0%, #66BB6A 100%);
        color: white;
        border: none;
        border-radius: 25px;
        height: 50px;
        font-size: 1.1em;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #262626;
        border-right: 1px solid #444;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------
# Initialization & Sidebar
# ---------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2927/2927347.png", width=80)
    st.title("Food Ranger")
    st.caption("AI-Powered Food Safety Analyst")
    st.markdown("---")
    
    st.markdown("### 🛠️ Configuration")
    # API Integration Status
    if "gemini_api_key" in st.secrets.get("general", {}):
        st.success("✅ Gemini API Connected")
    else:
        st.error("❌ Gemini API Key Missing")
        
    if "usda_api_key" in st.secrets.get("general", {}):
        st.success("✅ USDA API Connected")
    else:
        st.warning("⚠️ USDA API Key Missing (Fallback disabled)")

    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.info("Scan barcodes to instantly analyze ingredients for banned substances and health risks using Gemini 1.5 Pro and USDA databases.")

# ---------------------------
# Session State Setup
# ---------------------------
if 'product_data' not in st.session_state:
    st.session_state.product_data = None
if 'gemini_handler' not in st.session_state:
    try:
        st.session_state.gemini_handler = GeminiHandler()
    except Exception:
        st.session_state.gemini_handler = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# ---------------------------
# Main Layout
# ---------------------------
st.title("🛡️ Food Product Safety Analyzer")
st.markdown("### Discover what's really in your food")

# Input Section in a nice container ("Card" usage implied by layout)
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📸 Scan Product")
    input_tabs = st.tabs(["Upload Image", "Camera", "Manual Entry"])
    
    barcode = None
    
    with input_tabs[0]:
        uploaded_file = st.file_uploader("Upload product image", type=["jpg", "png", "jpeg"])
        if uploaded_file:
            image = Image.open(uploaded_file)
            st.image(image, use_column_width=True, caption="Uploaded Image")
            if st.button("🔍 Analyze Upload", key="btn_upload"):
                with st.spinner("Decoding barcode..."):
                    barcode = decode_barcode(image)

    with input_tabs[1]:
        camera_image = st.camera_input("Take a photo of the barcode")
        if camera_image:
            image = Image.open(camera_image)
            if st.button("🔍 Analyze Camera", key="btn_camera"):
                with st.spinner("Decoding barcode..."):
                    barcode = decode_barcode(image)

    with input_tabs[2]:
        manual_code = st.text_input("Enter Barcode Numbers manually")
        if st.button("🔍 Search Manual", key="btn_manual"):
            barcode = manual_code.strip()

    # Processing Logic
    if barcode:
        st.toast(f"Barcode Found: {barcode}", icon="📦")
        with st.spinner("🚀 Fetching product details from global databases..."):
            # Lookup
            raw_data = lookup_product(barcode)
            
            if raw_data:
                # Normalize & Analyze
                product = normalize_product_data(raw_data)
                
                # Parse Ingredients
                ingredients_list = parse_ingredients(product['ingredients_text'])
                product['parsed_ingredients'] = ingredients_list 
                
                # Risk Check
                banned_df = load_banned_ingredients("cloud_rangers/project/food_analysis/data/banned_ingredients.csv")
                risks = check_banned_ingredients(ingredients_list, banned_df)
                product['risks'] = risks
                
                # Health Score
                score = calculate_health_score(product.get('nutriments', {}))
                product['health_score'] = score
                
                # AI Explanation
                if st.session_state.gemini_handler:
                    try:
                        explanation = st.session_state.gemini_handler.explain_risks(
                            product['name'], 
                            ingredients_list, 
                            risks
                        )
                        product['explanation'] = explanation
                        st.session_state.gemini_handler.start_chat(product)
                    except Exception as e:
                        product['explanation'] = f"Could not generate AI explanation: {e}"
                
                st.session_state.product_data = product
                st.balloons()
            else:
                st.error("Product not found in OpenFoodFacts or USDA databases.")

with col2:
    if st.session_state.product_data:
        p = st.session_state.product_data
        
        # Product Header
        st.markdown(f"## {p['name']}")
        st.caption(f"Brand: {p['brand']} | Source: {p['source']}")
        
        # Summary Metrics
        m1, m2, m3 = st.columns(3)
        with m1:
            score = p.get('health_score', 0)
            color = "#43a047" if score > 70 else "#fb8c00" if score > 40 else "#e53935"
            st.markdown(f"""
            <div style="background-color: {color}; padding: 10px; border-radius: 10px; text-align: center;">
                <h2 style="margin:0; color:white;">{score}/100</h2>
                <p style="margin:0; color:white; font-size:0.8em;">Health Score</p>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            risk_count = len(p.get('risks', []))
            risk_color = "#e53935" if risk_count > 0 else "#43a047"
            st.markdown(f"""
            <div style="background-color: {risk_color}; padding: 10px; border-radius: 10px; text-align: center;">
                <h2 style="margin:0; color:white;">{risk_count}</h2>
                <p style="margin:0; color:white; font-size:0.8em;">Risks Found</p>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            nutri = p.get('nutriscore_grade', '?').upper()
            st.markdown(f"""
            <div style="background-color: #383838; border: 1px solid #555; padding: 10px; border-radius: 10px; text-align: center;">
                <h2 style="margin:0; color:white;">{nutri}</h2>
                <p style="margin:0; color: #aaa; font-size:0.8em;">Nutri-Score</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        
        # Tabs for details
        details_tab, ai_tab, chat_tab = st.tabs(["📊 Analysis Details", "🤖 Gemini Insight", "💬 Chat Assistant"])
        
        with details_tab:
            st.subheader("⚠️ Risk Analysis")
            risks = p.get('risks', [])
            if risks:
                for risk in risks:
                    lvl_class = f"risk-{risk['risk_level'].lower()}"
                    st.markdown(f"""
                    <div style="border-left: 4px solid #e53935; background-color: #2b2b2b; padding: 10px; margin-bottom: 10px; border-radius: 0 5px 5px 0;">
                        <span class="risk-badge {lvl_class}">{risk['risk_level']} Risk</span>
                        <strong>{risk['found_as'].title()}</strong>
                        <p style="margin: 5px 0 0 0; font-size: 0.9em; color: #ccc;">{risk['details']}</p>
                        <p style="margin: 2px 0 0 0; font-size: 0.8em; color: #888;">🚫 Banned in: {risk['banned_in']}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("No banned ingredients detected from our database.")
                
            with st.expander("Show Full Ingredients List"):
                st.write(p['ingredients_text'])

        with ai_tab:
            st.subheader("🤖 AI Health Breakdown")
            if 'explanation' in p:
                st.markdown(p['explanation'])
            else:
                st.info("AI explanation unavailable.")
                
        with chat_tab:
            st.subheader("💬 Ask about this product")
            # Chat Interface
            history_container = st.container()
            with history_container:
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])
            
            if prompt := st.chat_input("E.g., 'Is this safe for diabetics?'"):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.write(prompt)
                
                if st.session_state.gemini_handler:
                    with st.spinner("AI is thinking..."):
                        response = st.session_state.gemini_handler.send_message(prompt)
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"):
                        st.write(response)
                else:
                    st.error("Chat disconnected.")

    else:
        # Default Welcome State
        st.markdown("""
        <div style="text-align: center; padding: 50px;">
            <h3 style="color: #666;">👈 Scan a product to begin analysis</h3>
            <img src="https://cdn-icons-png.flaticon.com/512/1046/1046857.png" width="150" style="opacity: 0.5;">
        </div>
        """, unsafe_allow_html=True)
