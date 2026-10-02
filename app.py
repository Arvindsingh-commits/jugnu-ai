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

def get_jugnu_response(prompt_text):
    # Hindi ke liye Groq ke sabse acche models
    priority_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.2-11b-vision-preview",
        "llama-3.2-3b-preview"
    ]
    
    for m in priority_models:
        try:
            completion = client.chat.completions.create(
                model=m,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Aapka naam JUGNU hai. Aap Rewant Singh Bhati ke personal AI assistant hain. "
                            "Aapko sirf aur sirf aasan, saaf Hindi ya Hinglish me jawab dena hai. "
                            "Koi doosri bhasha (jaise Arabic, French) bilkul na bolein. "
                            "Hamesha 1 ya 2 chhote sentences me madhur aawaaz me bolne yogya reply dein."
                        )
                    },
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=80,
                temperature=0.6
            )
            return completion.choices[0].message.content.strip()
        except Exception:
            continue
            
    return "Namaste! Main JUGNU hoon. Kahiye main aapki kya madad kar sakta hoon?"

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — Superfast & Free")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Namaste! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
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
