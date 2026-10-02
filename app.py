import os
import io
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# --- Creator Profile Banner ---
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
    st.caption("निर्माता: **अरविंद सिंह** | आपका पर्सनल स्मार्ट साथी")

st.divider()

# --- Groq Client Setup ---
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

# Clear Hindi Audio Function
def play_audio(text):
    try:
        clean_text = text.split("```")[0].strip()
        if not clean_text:
            clean_text = "यहाँ आपका उत्तर है।"
        clean_text = clean_text[:250]
        
        sound = BytesIO()
        # Indian accent aur clear Hindi pronunciation ke liye tld="co.in"
        tts = gTTS(text=clean_text, lang="hi", tld="co.in", slow=False)
        tts.write_to_fp(sound)
        sound.seek(0)
        st.audio(sound, format="audio/mp3")
    except Exception:
        pass

def get_jugnu_response(prompt_text):
    system_prompt = (
        "तुम जुगनू (JUGNU) हो, एक विनम्र और अत्यंत समझदार AI साथी। "
        "नियम 1: हमेशा उत्तर शुद्ध देवनागरी हिंदी लिपि में ही लिखो ताकि आवाज़ साफ़ आए। रोमन/हिंग्लिश अक्षरों का इस्तेमाल न करो। "
        "नियम 2: अगर कोई पूछे कि तुम्हें किसने बनाया है, तो साफ़ कहो: 'मुझे अरविंद सिंह ने बनाया है।' "
        "नियम 3: अगर कोई पूछे कि तुम्हें जिसने बनाया है उसके बारे में बताओ या अरविंद सिंह के बारे में बताओ, तो ठीक यही कहो: 'अरविंद सिंह का गाँव दूजासर है और वो अभी श्री मोहनगढ़ में रहते हैं।' "
        "नियम 4: उत्तर हमेशा केवल 1 या 2 छोटे वाक्यों में स्वाभाविक हिंदी में दो।"
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

    return f"Error: {last_error}" if last_error else "माफ़ कीजिए, कोई सक्रिय मॉडल नहीं मिला।"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]

# Message History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# Voice Input Box
st.write("")
with st.container(border=True):
    st.markdown("🎙️ **JUGNU से बोलकर पूछने के लिए नीचे रिकॉर्ड करें:**")
    voice_input = st.audio_input("Record audio", key="jugnu_mic", label_visibility="collapsed")

# Text Input
user_text = st.chat_input("यहाँ लिखकर पूछिए...")

# Handle Voice
if voice_input is not None:
    audio_bytes = voice_input.getvalue()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != audio_bytes):
        st.session_state.last_voice = audio_bytes
        with st.spinner("आपकी आवाज़ सुनी जा रही है..."):
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
            with st.spinner("जुगनू सोच रहा है..."):
                reply = get_jugnu_response(recognized_text)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()

# Handle Text
elif user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("जुगनू सोच रहा है..."):
        reply = get_jugnu_response(user_text)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
