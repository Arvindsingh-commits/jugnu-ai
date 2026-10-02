import os
import io
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# --- Creator Profile Banner (Auto Image Detector) ---
col1, col2 = st.columns([1, 4])
with col1:
    creator_img = None
    check_list = [
        "creater 1.jpg", "creater 1.png", "creater 1.jpeg", "creater 1.webp",
        "creater1.jpg", "creater1.png", "creater1.jpeg",
        "creater.jpg", "creater.png", "creater.jpeg",
        "creator 1.jpg", "creator 1.png", "creator 1.jpeg", "creator 1.webp",
        "creator1.jpg", "creator1.png", "creator1.jpeg",
        "creator.jpg", "creator.png", "creator.jpeg"
    ]
    for fname in check_list:
        if os.path.exists(fname):
            creator_img = fname
            break
            
    if not creator_img:
        for f in os.listdir("."):
            lower_f = f.lower()
            if any(lower_f.endswith(ext) for ext in [".jpg", ".png", ".jpeg", ".webp"]):
                creator_img = f
                break

    if creator_img:
        st.image(creator_img, width=95)
    else:
        st.markdown("### 👑")

with col2:
    st.markdown("### ✨ JUGNU AI Assistant")
    st.caption("Nirmata: **Arvind Singh** | Aapka personal smart saathi")

st.divider()

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
        "CRITICAL RULE 1: Agar koi pooche ki tumhe kisne banaya hai, toh kaho: 'Mujhe Arvind Singh ne banaya hai.' "
        "CRITICAL RULE 2: Agar koi pooche ki tumhe jisne banaya hai uske bare me batao ya Arvind Singh ke bare me batao, toh seedhe aur saaf kaho: 'Arvind Singh ka gav Doojasor ha or vo abhi Shri mohangarh me rahte ha.' "
        "CRITICAL RULE 3: Hamesha saral Hindi ya Hinglish me 1-2 sentences me hi seedha jawab do. "
        "CRITICAL RULE 4: Arabic ya koi anya bhasha bilkul mat bolo."
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
                temperature=0.3
            )
            reply = completion.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as err:
            last_error = str(err)
            continue

    return f"Error: {last_error}" if last_error else "Maaf kijiye, koi active model nahi mila."

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

# Voice Input Box
st.write("")
with st.container(border=True):
    st.markdown("🎙️ **JUGNU se bolkar poochne ke liye neeche record karein:**")
    voice_input = st.audio_input("Record audio", key="jugnu_mic", label_visibility="collapsed")

# Text Input Box
user_text = st.chat_input("Yahan likh kar poochiye...")

# Handle Voice Input
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

# Handle Text Input
elif user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("JUGNU soch raha hai..."):
        reply = get_jugnu_response(user_text)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
