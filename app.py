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
        # कोड या लंबे उत्तर होने पर केवल शुरुआती पंक्तियों की आवाज़ बनेगी
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
    # केवल उच्च गुणवत्ता वाले मॉडल जो हिंदी बेहतर समझते हैं
    reliable_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile"
    ]
    
    system_prompt = (
        "तुम जुगनू (JUGNU) नाम के एक बुद्धिमान और विनम्र AI सहायक हो। "
        "तुम्हारा काम केवल स्वाभाविक, शुद्ध और सरल हिंदी या हिंग्लिश में बातचीत करना है। "
        "कोई बेतुकी बात या निर्देश न दोहराएँ। "
        "यदि यूजर 'bye' या विदाई कहे, तो विनम्रता से 'अलविदा! अपना ध्यान रखिएगा।' जैसा संक्षिप्त उत्तर दो। "
        "सामान्य बातचीत में 1 से 2 छोटे वाक्यों में ही उत्तर दो।"
    )

    for model_name in reliable_models:
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
            ans = completion.choices[0].message.content.strip()
            if ans:
                return ans
        except Exception:
            continue

    return "अलविदा! फिर मिलते हैं।"

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
