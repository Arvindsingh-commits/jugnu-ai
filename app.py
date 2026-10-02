import os
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# API Key लोड करें
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def play_audio(text):
    try:
        # अगर जवाब में बहुत बड़ा कोड हो तो आवाज़ सिर्फ पहले 250 अक्षरों की बनेगी
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
        "आप जुगनू (JUGNU) हैं, एक मददगार AI साथी। "
        "हमेशा हिंदी (Hindi) या हिंग्लिश (Hinglish) में बात करें। "
        "अगर यूजर कोड माँगे, तो स्पष्ट और सही कोड दें। "
        "अरबी या किसी अन्य विदेशी भाषा का प्रयोग बिल्कुल न करें।"
    )
    
    # चालू और स्टेबल मॉडल्स
    candidate_models = [
        "llama-3.3-70b-versatile",
        "llama3-70b-8192",
        "llama-3.1-8b-instant"
    ]
    
    last_err = ""
    for model_id in candidate_models:
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
            res = completion.choices[0].message.content.strip()
            if res:
                return res
        except Exception as e:
            last_err = str(e)
            continue
            
    return f"त्रुटि (Error): {last_err}"

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — Superfast & Free")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]

# स्क्रीन पर मैसेज दिखाना
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
