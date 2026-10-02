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
        clean_text = text.split("```")[0].strip()
        if not clean_text:
            clean_text = "यहाँ आपका उत्तर तैयार है।"
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
        "तुम जुगनू (JUGNU) हो, एक विनम्र और सरल हिंदी AI सहायक। "
        "यूज़र के सवाल के अनुसार केवल स्वाभाविक हिंदी या हिंग्लिश में 1 से 2 छोटे वाक्यों में उत्तर दो। "
        "यूज़र के सवाल का सटीक जवाब दो और कोई बेतुकी बात मत बोलो।"
    )

    # Groq खाते से सक्रिय मॉडल्स की ताज़ा सूची प्राप्त करना
    try:
        models_data = client.models.list().data
        active_ids = [m.id for m in models_data]
        # ऑडियो, विज़न और गार्ड मॉडल्स को छोड़कर टेक्स्ट मॉडल्स चुनें
        usable_models = [
            m for m in active_ids 
            if not any(bad in m.lower() for bad in ["whisper", "guard", "moderation", "vision"])
        ]
    except Exception as e:
        return f"Groq Connection Error: {str(e)}"

    last_error = ""
    for model_name in usable_models:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=150,
                temperature=0.5
            )
            reply = completion.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as err:
            last_error = str(err)
            continue

    return f"Error: {last_error}" if last_error else "माफ़ कीजिए, कोई सक्रिय मॉडल नहीं मिला।"

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — Superfast & Free")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]

# स्क्रीन पर पुराने मैसेज दिखाना
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
