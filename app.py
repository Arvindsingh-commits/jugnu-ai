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

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

# Purane messages dikhana
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# --- INPUT OPTIONS: Text ya Mic ---
col1, col2 = st.columns([1, 1])

# Mic se bolne ke liye
with col1:
    voice_input = st.audio_input("🎙️ Bolkar poochiye:")

# Type karne ke liye
user_text = st.chat_input("Ya yahan type karke poochiye...")

# Check karein input kis taraf se aaya
user_prompt = None
is_audio_prompt = False

if voice_input is not None:
    is_audio_prompt = True
elif user_text:
    user_prompt = user_text

if is_audio_prompt:
    with st.chat_message("user"):
        st.audio(voice_input)
    st.session_state.messages.append({"role": "user", "content": "🎙️ [Aapki Voice Message]"})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("JUGNU aapki aawaaz sun raha hai..."):
            try:
                audio_bytes = voice_input.read()
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=voice_input.type),
                        "You are JUGNU, a polite Hindi/Hinglish personal AI assistant. "
                        "Listen carefully and reply strictly in 1 to 2 short sentences in friendly Hindi or Hinglish."
                    ]
                )
                reply = response.text.strip() if response and response.text else "Maaf kijiye, samajh nahi aaya."
            except Exception as e:
                reply = "Aapki aawaaz process karne me dikkat aayi. Kripya dobara bolein."

        message_placeholder.write(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        play_audio(reply)

elif user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.write(user_prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("JUGNU soch raha hai..."):
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=(
                        "You are JUGNU, a polite Hindi/Hinglish personal AI assistant. "
                        "Reply strictly in 1 to 2 short sentences in friendly Hindi or Hinglish. "
                        f"User message: {user_prompt}"
                    )
                )
                reply = response.text.strip() if response and response.text else "Kuch dikkat aayi, kripya dobara poochein."
            except Exception as e:
                reply = "Google server busy hai. Kripya dobara poochein."

        message_placeholder.write(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        play_audio(reply)
