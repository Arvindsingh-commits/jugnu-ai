import os
import time
from io import BytesIO
import streamlit as st
from google import genai
from dotenv import load_dotenv
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def play_audio(text):
    try:
        sound = BytesIO()
        tts = gTTS(text=text, lang='hi', slow=False)
        tts.write_to_fp(sound)
        sound.seek(0)
        st.audio(sound, format="audio/mp3")
    except Exception as e:
        pass

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — 24/7 online & bolne wala")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

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
            play_audio(reply)
        else:
            err_msg = "Google server busy hai. Kripya dobara poochiye."
            message_placeholder.error(err_msg)
            st.session_state.messages.append({"role": "assistant", "content": err_msg})
