import os
import time
from io import BytesIO
import streamlit as st
from google import genai
from google.genai import types
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
    except Exception:
        pass

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — 24/7 online, sunne aur bolne wala")

# Messages state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

# Inputs
user_text = st.chat_input("Yahan type karke poochiye...")

with st.container(border=True):
    st.markdown("#### 🎙️ JUGNU se Bolkar Baat Karein")
    voice_input = st.audio_input("Mic se bolein", label_visibility="collapsed")

# Handle New Inputs
if voice_input is not None:
    # Check if this voice audio is already processed to avoid infinite loop
    voice_bytes = voice_input.read()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != voice_bytes):
        st.session_state.last_voice = voice_bytes
        st.session_state.messages.append({"role": "user", "content": "🎙️ [Voice Command]"})
        
        with st.spinner("JUGNU aapki aawaaz sun raha hai..."):
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[
                        types.Part.from_bytes(data=voice_bytes, mime_type=voice_input.type),
                        "You are JUGNU, a polite Hindi/Hinglish personal AI voice assistant. "
                        "Listen carefully and reply strictly in 1 to 2 short sentences in friendly Hindi or Hinglish."
                    ]
                )
                reply = response.text.strip() if response and response.text else "Maaf kijiye, samajh nahi aaya."
            except Exception:
                reply = "Aapki aawaaz sunne me dikkat aayi. Kripya dobara bolein."
        
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

elif user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("JUGNU soch raha hai..."):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=(
                    "You are JUGNU, a polite Hindi/Hinglish personal AI assistant. "
                    "Reply strictly in 1 to 2 short sentences in friendly Hindi or Hinglish. "
                    f"User message: {user_text}"
                )
            )
            reply = response.text.strip() if response and response.text else "Maaf kijiye, dobara poochein."
        except Exception:
            reply = "Google server busy hai. Kripya dobara poochein."

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()

# Display all chat messages cleanly
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])
