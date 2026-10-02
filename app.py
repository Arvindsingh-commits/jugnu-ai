import os
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# Load Groq Key
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def play_audio(text):
    try:
        sound = BytesIO()
        tts = gTTS(text=text, lang="hi", slow=False)
        tts.write_to_fp(sound)
        sound.seek(0)
        st.audio(sound, format="audio/mp3")
    except Exception:
        pass

@st.cache_resource
def get_available_groq_model():
    # Groq account ke active models me se text chat model select karna
    try:
        models_data = client.models.list()
        active_ids = [m.id for m in models_data.data]
        # Text/Chat ke liye common Groq models check karein
        for candidate in active_ids:
            if any(term in candidate.lower() for term in ["llama", "mixtral", "gemma"]) and "whisper" not in candidate.lower():
                return candidate
        return active_ids[0] if active_ids else "llama3-8b-8192"
    except Exception:
        return "llama3-8b-8192"

def get_jugnu_response(prompt_text):
    model_to_use = get_available_groq_model()
    try:
        completion = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {
                    "role": "system",
                    "content": "You are JUGNU, a polite, helpful Hindi/Hinglish personal AI assistant. Keep responses strictly within 1 to 2 short sentences in natural Hindi or Hinglish so it sounds great on voice."
                },
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=100
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — Superfast & Free")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

# Screen par messages dikhana
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# Text Input
user_text = st.chat_input("Yahan likh kar poochiye...")

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("JUGNU soch raha hai..."):
        reply = get_jugnu_response(user_text)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
