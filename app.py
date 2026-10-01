import os
import time
from io import BytesIO
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

st.markdown("", unsafe_allow_html=True)

# API Key load karein: Streamlit secrets pehle, fir env
load_dotenv()
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
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
st.caption("Aapka personal AI saathi — 24/7 online")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

# Screen par chat messages dikhana
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# Bottom Mic Box
st.write("")
with st.container(border=True):
    st.markdown("🎙️ **JUGNU se bolkar poochne ke liye neeche record karein:**")
    voice_input = st.audio_input("Record audio", label_visibility="collapsed")

# Text Input
user_text = st.chat_input("Yahan likh kar poochiye...")

# Handle Voice Input
if voice_input is not None:
    audio_data = voice_input.getvalue()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != audio_data):
        st.session_state.last_voice = audio_data
        st.session_state.messages.append({"role": "user", "content": "🎙️ [Aapka Voice Message]"})
        
        reply = None
        with st.spinner("JUGNU aapki aawaaz sun raha hai..."):
            mtype = voice_input.type if hasattr(voice_input, 'type') and voice_input.type else "audio/wav"
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(data=audio_data, mime_type=mtype),
                        "You are JUGNU, a friendly Hindi personal AI voice assistant. Listen to the user audio and reply strictly in 1 or 2 short sentences in polite Hindi or Hinglish."
                    ]
                )
                if response and response.text:
                    reply = response.text.strip()
            except Exception as e:
                reply = f"Error: {str(e)}"

        if not reply:
            reply = "Maaf kijiye, aawaaz samajh nahi aayi. Kripya dobara bolein."
            
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

# Handle Text Input
elif user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    reply = None
    with st.spinner("JUGNU soch raha hai..."):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(
                    "You are JUGNU, a polite Hindi/Hinglish personal AI assistant. "
                    "Reply strictly in 1 to 2 short sentences in friendly Hindi or Hinglish. "
                    f"User question: {user_text}"
                )
            )
            if response and response.text:
                reply = response.text.strip()
        except Exception as e:
            reply = f"Error: {str(e)}"

    if not reply:
        reply = "Kripya dobara poochiye."

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
