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
    user_prompt = (
        "You are JUGNU, a polite Hindi/Hinglish personal AI assistant. "
        "Reply strictly in 1 to 2 short sentences in friendly Hindi or Hinglish. "
        f"User message: {prompt_text}"
    )

    # 1. Agar working model pehle mil chuka hai toh direct call karein
    if "working_model" in st.session_state:
        try:
            completion = client.chat.completions.create(
                model=st.session_state["working_model"],
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=100
            )
            return completion.choices[0].message.content.strip()
        except Exception:
            st.session_state.pop("working_model", None)

    # 2. Account ke saare active models Groq se live mangwayein
    try:
        all_models = [m.id for m in client.models.list().data]
        # Audio aur Guard models ko chhodkar chat models filter karein
        chat_candidates = [
            mid for mid in all_models 
            if not any(bad in mid.lower() for bad in ["whisper", "guard", "moderation"])
        ]
    except Exception as e:
        return f"API Error: {str(e)}"

    # 3. Jo model chal jaye, usko select karke reply le aayein
    for mid in chat_candidates:
        try:
            completion = client.chat.completions.create(
                model=mid,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=100
            )
            st.session_state["working_model"] = mid
            return completion.choices[0].message.content.strip()
        except Exception:
            continue

    return "Maaf kijiye, koi working model nahi mila. Kripya thodi der baad koshish karein."

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
