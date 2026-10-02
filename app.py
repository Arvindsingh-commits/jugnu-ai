import os
import io
import base64
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# --- Theme State ---
if "applied_theme" not in st.session_state:
    st.session_state.applied_theme = "Default White"
if "uploaded_bg_bytes" not in st.session_state:
    st.session_state.uploaded_bg_bytes = None

# --- Sidebar ---
st.sidebar.title("🎨 JUGNU Theme Settings")
selected_theme = st.sidebar.selectbox(
    "Background chunein:",
    ["Default White", "Dark Black", "Creator Photo", "Apni Photo Upload Karein"],
    index=["Default White", "Dark Black", "Creator Photo", "Apni Photo Upload Karein"].index(st.session_state.applied_theme)
)

uploaded_file = None
if selected_theme == "Apni Photo Upload Karein":
    uploaded_file = st.sidebar.file_uploader("Photo chunein (JPG/PNG)", type=["jpg", "jpeg", "png"])

if st.sidebar.button("💾 Save Theme", use_container_width=True):
    st.session_state.applied_theme = selected_theme
    if selected_theme == "Apni Photo Upload Karein" and uploaded_file is not None:
        st.session_state.uploaded_bg_bytes = uploaded_file.getvalue()
    st.sidebar.success("Theme save ho gayi!")
    st.rerun()

# --- Full Screen Background Engine ---
def apply_active_theme():
    cur = st.session_state.applied_theme
    
    # Base CSS: Background containers ko transparent karna taaki peeche ki image dikhe
    base_transparency = """
    
    """

    if cur == "Creator Photo":
        found = None
        for name in ["creator.jpg", "creator.png", "creator.jpeg", "creator.JPG", "creator.PNG"]:
            if os.path.exists(name):
                found = name
                break
        if found:
            with open(found, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            st.markdown(
                base_transparency + f"""
