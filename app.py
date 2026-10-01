import os
import time
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from dotenv import load_dotenv

# Page setting
st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# Footer aur menu hide karna
hide_style = """
    
"""
st.markdown(hide_style, unsafe_allow_html=True)

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize Gemini Client
client = genai.Client(api_key=api_key)

# Mobile browser friendly speech button
def speak_button(text, msg_index):
    clean_text = text.replace('"', '\\"').replace("'", "\\'").replace("\n", " ")
    button_html = f"""
