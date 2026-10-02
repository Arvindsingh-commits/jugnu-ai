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
    system_instruction = (
        "Aapka naam JUGNU hai. Aap ek smart, polite Hindi AI assistant hain. "
        "User ke sawal ka seedha, natural Hindi ya Hinglish me 1-2 line me reply dein."
    )
    
    # Live available models check karein
    try:
        model_list = [m.id for m in client.models.list().data]
        # Text conversation models filter karein (whisper/audio chhod kar)
        usable_models = [m for m in model_list if not any(x in m.lower() for x in ["whisper", "guard", "moderation", "vision"])]
    except Exception as e:
        return f"Model List Error: {str(e)}"

    last_error = ""
    for model_id in usable_models:
        try:
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=120,
                temperature=0.7
            )
            return completion.choices[0].message.content.strip()
        except Exception as err:
            last_error = str(err)
            continue

    return f"Groq Error: {last_error}" if last_error else "Koi active model nahi mila."

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
