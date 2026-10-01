import os
import time
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from dotenv import load_dotenv

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def speak_button(text, msg_index):
    clean_text = text.replace('"', ' ').replace("'", ' ').replace("\n", " ")
    button_html = f"""
    
        🔊 Suniye
    
    """
    components.html(button_html, height=45)

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — 24/7 online & bolne wala")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant":
            speak_button(msg["content"], i)

user_input = st.chat_input("JUGNU se kuch bhi poochiye...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        prompt = (
            "You are JUGNU, a polite, intelligent personal voice assistant. "
            "Reply strictly in 1 to 2 very short, natural sentences in Hindi or Hinglish "
            f"so it sounds completely clear when spoken aloud. Question: {user_input}"
        )
        
        reply = None
        for attempt in range(3):
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
                    if "503" in str(e) and attempt < 2:
                        time.sleep(2)
                        continue

        if reply:
            message_placeholder.write(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            speak_button(reply, len(st.session_state.messages))
        else:
            err_msg = "Google server thoda busy hai. Kripya thodi der baad dobara koshish karein."
            message_placeholder.error(err_msg)
            st.session_state.messages.append({"role": "assistant", "content": err_msg})
