import os
import io
import base64
from io import BytesIO
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# --- Session State for Theme ---
if "applied_theme" not in st.session_state:
    st.session_state.applied_theme = "Default White"
if "custom_bg_b64" not in st.session_state:
    st.session_state.custom_bg_b64 = None

# --- Sidebar Controls ---
st.sidebar.title("🎨 JUGNU Theme Settings")
selected_theme = st.sidebar.selectbox(
    "Background chunein:",
    ["Default White", "Dark Black", "Creator Photo", "Apni Photo Upload Karein"],
    index=["Default White", "Dark Black", "Creator Photo", "Apni Photo Upload Karein"].index(st.session_state.applied_theme)
)

uploaded_file = None
if selected_theme == "Apni Photo Upload Karein":
    uploaded_file = st.sidebar.file_uploader("Photo chunein (JPG/PNG)", type=["jpg", "jpeg", "png"])

if st.sidebar.button("💾 Save Theme", use_container_width=True):
    st.session_state.applied_theme = selected_theme
    if selected_theme == "Apni Photo Upload Karein" and uploaded_file is not None:
        st.session_state.custom_bg_b64 = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
    st.sidebar.success("Theme save ho gayi!")
    st.rerun()

# --- Force Background JavaScript Injector ---
def apply_theme_system():
    cur = st.session_state.applied_theme
    b64_img = ""
    is_image = False
    is_dark = False

    if cur == "Dark Black":
        is_dark = True
    elif cur == "Creator Photo":
        found = None
        for name in ["creator.jpg", "creator.png", "creator.jpeg", "creator.JPG", "creator.PNG"]:
            if os.path.exists(name):
                found = name
                break
        if found:
            with open(found, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")
            is_image = True
        else:
            st.sidebar.warning("⚠️ GitHub par 'creator.jpg' nahi mili!")
    elif cur == "Apni Photo Upload Karein" and st.session_state.custom_bg_b64:
        b64_img = st.session_state.custom_bg_b64
        is_image = True

    # Direct DOM injection via JavaScript to override Streamlit styling completely
    if is_image:
        js = f"""
        
        """
        components.html(js, height=0)
        st.markdown(
            """
            
            """,
            unsafe_allow_html=True
        )
    elif is_dark:
        js = """
        
        """
        components.html(js, height=0)
        st.markdown(
            """
            
            """,
            unsafe_allow_html=True
        )
    else:
        js = """
        
        """
        components.html(js, height=0)
        st.markdown("", unsafe_allow_html=True)

apply_theme_system()

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
        "CRITICAL RULE 1: Agar koi pooche ki tumhe kisne banaya hai ya tumhara creator kaun hai, toh saaf aur seedhe kaho: 'Mujhe Arvind Singh ne banaya hai.' "
        "CRITICAL RULE 2: Hamesha saral Hindi ya Hinglish me 1-2 sentences me hi seedha jawab do. "
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
                temperature=0.4
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

# Message history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# Audio recorder
st.write("")
with st.container(border=True):
    st.markdown("🎙️ **JUGNU se bolkar poochne ke liye neeche record karein:**")
    voice_input = st.audio_input("Record audio", key="jugnu_mic", label_visibility="collapsed")

# Text input
user_text = st.chat_input("Yahan likh kar poochiye...")

# Voice handling
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

# Text handling
elif user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("JUGNU soch raha hai..."):
        reply = get_jugnu_response(user_text)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
