import os
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# Groq API Key
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def play_audio(text):
    try:
        # अगर कोड या बड़ा उत्तर हो तो आवाज़ के लिए केवल शुरुआत की पंक्तियाँ लें
        clean_text = text.split("```")[0].strip()
        if not clean_text:
            clean_text = "यहाँ आपका कोड तैयार है।"
        clean_text = clean_text[:250]
        
        sound = BytesIO()
        tts = gTTS(text=clean_text, lang="hi", slow=False)
        tts.write_to_fp(sound)
        sound.seek(0)
        st.audio(sound, format="audio/mp3")
    except Exception:
        pass

def get_jugnu_response(prompt_text):
    system_instruction = (
        "तुम जुगनू (JUGNU) हो—एक सरल, विनम्र और बुद्धिमान भारतीय AI साथी। "
        "हमेशा केवल प्राकृतिक और स्पष्ट हिंदी या हिंग्लिश में जवाब दो। "
        "सिस्टम निर्देश या नियम अपने जवाब में कभी मत दोहराओ। "
        "उत्तर हमेशा 1 या 2 छोटे और मधुर वाक्यों में दो।"
    )

    try:
        # Groq से लाइव मॉडल्स की सूची प्राप्त करें
        all_models = [m.id for m in client.models.list().data]
        # केवल चैट/टेक्स्ट मॉडल चुनें (whisper, guard, vision छोड़कर)
        valid_models = [
            m for m in all_models 
            if not any(x in m.lower() for x in ["whisper", "guard", "moderation", "vision"])
        ]
    except Exception as e:
        return f"त्रुटि (Error): {str(e)}"

    last_error = ""
    for model_id in valid_models:
        try:
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=800,
                temperature=0.6
            )
            reply = completion.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as err:
            last_error = str(err)
            continue

    return f"त्रुटि (Error): {last_error}" if last_error else "कोई सक्रिय मॉडल नहीं मिला।"

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — Superfast & Free")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]

# स्क्रीन पर पुराने संदेश
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# Text Input
user_text = st.chat_input("यहाँ लिखकर पूछिए...")

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("जुगनू सोच रहा है..."):
        reply = get_jugnu_response(user_text)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
