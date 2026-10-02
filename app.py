import os
import io
import base64
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# --- Theme aur Background Settings (Sidebar) ---
st.sidebar.title("🎨 JUGNU Theme Settings")
theme_choice = st.sidebar.selectbox(
    "Background chunein:",
    ["Default White", "Dark Black", "Creator Photo (Arvind & Metab)", "Apni Photo Upload Karein"]
)

custom_bg_file = None
if theme_choice == "Apni Photo Upload Karein":
    custom_bg_file = st.sidebar.file_uploader("Apni photo upload karein (JPG/PNG)", type=["jpg", "jpeg", "png"])

def apply_background(choice, uploaded_file):
    css = ""
    if choice == "Default White":
        css = """
        
        """
    elif choice == "Dark Black":
        css = """
        
        """
    elif choice == "Creator Photo (Arvind & Metab)":
        if os.path.exists("creator.jpg"):
            with open("creator.jpg", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            css = f"""
            
            """
    elif choice == "Apni Photo Upload Karein" and uploaded_file is not None:
        b64 = base64.b64encode(uploaded_file.getvalue()).decode()
        css = f"""
        
        """
    
    if css:
        st.markdown(css, unsafe_allow_html=True)
    else:
        st.markdown("", unsafe_allow_html=True)

apply_background(theme_choice, custom_bg_file)

# --- Groq Client Setup ---
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def play_audio(text):
    try:
        clean_text = text.split("```")[0].strip()
        if not clean_text:
            clean_text = "Yahan aapka uttar hai."
        clean_text = clean_text[:250]
        
        sound = BytesIO()
        tts = gTTS(text=clean_text, lang="hi", slow=False)
        tts.write_to_fp(sound)
        sound.seek(0)
        st.audio(sound, format="audio/mp3")
    except Exception:
        pass

def get_jugnu_response(prompt_text):
    system_prompt = (
        "Tum JUGNU ho, ek vinamra, smart aur helpful Hindi AI assistant. "
        "CRITICAL RULE 1: Agar koi pooche ki tumhe kisne banaya hai, toh kaho: 'Mujhe Arvind Singh aur Metab Singh ne banaya hai.' "
        "CRITICAL RULE 2: Hamesha saral Hindi ya Hinglish me 1-2 sentences me jawab do. "
        "CRITICAL RULE 3: Arabic ya koi anya bhasha bilkul mat bolo."
    )

    try:
        models_data = client.models.list().data
        active_ids = [m.id for m in models_data]
        usable_models = [
            m for m in active_ids 
            if not any(bad in m.lower() for bad in ["whisper", "guard", "moderation", "vision"])
        ]
    except Exception as e:
        return f"Groq Error: {str(e)}"

    last_error = ""
    for model_name in usable_models:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=200,
                temperature=0.5
            )
            reply = completion.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as err:
            last_error = str(err)
            continue

    return f"Error: {last_error}" if last_error else "Maaf kijiye, koi active model nahi mila."

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — Superfast & Free")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Namaste! Main JUGNU hoon. Kahiye aaj main aapki kya madad kar sakta hoon?"}
    ]

# Purane messages dikhana
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# Voice Recording Box
st.write("")
with st.container(border=True):
    st.markdown("🎙️ **JUGNU se bolkar poochne ke liye neeche record karein:**")
    voice_input = st.audio_input("Record audio", key="jugnu_mic", label_visibility="collapsed")

# Text Input Box
user_text = st.chat_input("Yahan likh kar poochiye...")

# Voice Process
if voice_input is not None:
    audio_bytes = voice_input.getvalue()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != audio_bytes):
        st.session_state.last_voice = audio_bytes
        with st.spinner("Aapki aawaaz suni jaa rahi hai..."):
            recognized_text = ""
            try:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "recording.wav"
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3-turbo",
                    language="hi"
                )
                recognized_text = transcription.text.strip()
            except Exception as e:
                st.error(f"Voice error: {str(e)}")

        if recognized_text:
            st.session_state.messages.append({"role": "user", "content": f"🎙 {recognized_text}"})
            with st.spinner("JUGNU soch raha hai..."):
                reply = get_jugnu_response(recognized_text)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()

# Text Process
elif user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("JUGNU soch raha hai..."):
        reply = get_jugnu_response(user_text)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
