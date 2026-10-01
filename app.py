import os
import time
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from dotenv import load_dotenv

# Page setting
st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize Gemini Client
client = genai.Client(api_key=api_key)

# Function to speak text in browser/mobile using HTML5 Speech Synthesis
def speak_in_browser(text):
    clean_text = text.replace('"', '\\"').replace("'", "\\'").replace("\n", " ")
    tts_code = f"""
    
    """
    components.html(tts_code, height=0, width=0)

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — 24/7 online & bolne wala")

# Session state me messages store karna
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

# Purane messages dikhana
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# User input box
user_input = st.chat_input("JUGNU se kuch bhi poochiye...")

if user_input:
    # User message screen par dikhana
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Gemini AI se response lena
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        prompt = (
            "You are JUGNU, a polite, intelligent, and helpful personal voice assistant. "
            "Reply strictly in 1 to 3 short, friendly sentences in Hindi or Hinglish "
            f"so it sounds completely natural when spoken aloud. User message: {user_input}"
        )
        
        reply = None
        max_retries = 3
        
        for attempt in range(max_retries):
            with st.spinner("JUGNU soch raha hai..."):
                try:
                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=prompt,
                    )
                    if response and response.text:
                        reply = response.text.strip()
                        break
                except Exception as e:
                    if "503" in str(e) and attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        last_err = str(e)

        if reply:
            message_placeholder.write(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            speak_in_browser(reply)
        else:
            err_msg = "Google server thoda busy hai. Kripya 10 second baad dobara poochein."
            message_placeholder.error(err_msg)
            st.session_state.messages.append({"role": "assistant", "content": err_msg})
