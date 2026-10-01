import os
import time
import streamlit as st
from google import genai
from dotenv import load_dotenv

# Page setting
st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize Gemini Client
client = genai.Client(api_key=api_key)

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — 24/7 online")

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

    # Gemini AI se response lena with retry
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        prompt = (
            "You are JUGNU, a polite, intelligent, and helpful personal AI assistant. "
            "Reply naturally in Hindi or Hinglish in a friendly, conversational tone. "
            f"User message: {user_input}"
        )
        
        reply = None
        max_retries = 3
        
        for attempt in range(max_retries):
            with st.spinner(f"JUGNU soch raha hai... (Koshish {attempt + 1}/{max_retries})"):
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
        else:
            err_msg = "Google server par abhi bohot traffic hai. Kripya 15-20 second baad dobara try karein."
            message_placeholder.error(err_msg)
            st.session_state.messages.append({"role": "assistant", "content": err_msg})