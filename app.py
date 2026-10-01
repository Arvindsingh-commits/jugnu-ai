import os
import time
from io import BytesIO
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# Default Streamlit footer hide karein
st.markdown("", unsafe_allow_html=True)

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

def ask_gemini_with_retry(contents_payload):
    models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents_payload,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                time.sleep(1.5)
    return "Maaf kijiye, abhi network thoda busy hai. Kripya 5 second baad dobara bolein ya likhein."

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — 24/7 online")

# Session state me messages initialize karein
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

# 1. Sabse pehle saare CHAT MESSAGES dikhayenge (Screen par upar)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# 2. Messages ke theek neeche fix MIC BOX banayenge
st.write("")
with st.container(border=True):
    st.markdown("🎙️ **JUGNU se bolkar poochne ke liye neeche record karein:**")
    voice_input = st.audio_input("Record audio", label_visibility="collapsed")

# 3. Screen ke pin bottom par typing chat input
user_text = st.chat_input("Yahan likh kar poochiye...")

# --- Process User Inputs ---
if voice_input is not None:
    voice_bytes = voice_input.read()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != voice_bytes):
        st.session_state.last_voice = voice_bytes
        st.session_state.messages.append({"role": "user", "content": "🎙️ [Aapka Voice Message]"})
        
        with st.spinner("JUGNU aapki aawaaz sun raha hai..."):
            prompt_content = [
                types.Part.from_bytes(data=voice_bytes, mime_type=voice_input.type),
                "You are JUGNU, a polite, smart Hindi/Hinglish personal AI voice assistant. "
                "Listen carefully and reply strictly in 1 to 2 short sentences in friendly Hindi or Hinglish."
            ]
            reply = ask_gemini_with_retry(prompt_content)
            
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

elif user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("JUGNU soch raha hai..."):
        prompt_content = (
            "You are JUGNU, a polite Hindi/Hinglish personal AI assistant. "
            "Reply strictly in 1 to 2 short sentences in friendly Hindi or Hinglish. "
            f"User message: {user_text}"
        )
        reply = ask_gemini_with_retry(prompt_content)
        
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
