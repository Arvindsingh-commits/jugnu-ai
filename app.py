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
    # कड़ा सिस्टम निर्देश: केवल हिंदी या हिंग्लिश
    system_instruction = (
        "You are JUGNU, an AI assistant. "
        "CRITICAL RULE: You must ALWAYS respond ONLY in pure Hindi (Devanagari) or natural conversational Hinglish. "
        "DO NOT use Arabic, Persian, or any other foreign language under any circumstances. "
        "Keep your reply helpful, friendly, and within 2 to 4 sentences."
    )
    
    # सबसे स्थिर और अच्छी हिंदी समझने वाले मॉडल्स
    preferred_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.2-3b-preview",
        "llama-3.2-1b-preview"
    ]
    
    for model_id in preferred_models:
        try:
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=250,
                temperature=0.5
            )
            reply = completion.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception:
            continue

    # अगर ऊपर का कोई मॉडल न चले तो ऑटो-लिस्ट में से कोशिश करें
    try:
        model_list = [m.id for m in client.models.list().data if "llama" in m.id.lower() and "guard" not in m.id.lower()]
        for m_id in model_list:
            try:
                completion = client.chat.completions.create(
                    model=m_id,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt_text}
                    ],
                    max_tokens=250,
                    temperature=0.5
                )
                return completion.choices[0].message.content.strip()
            except Exception:
                continue
    except Exception as e:
        return f"Error: {str(e)}"

    return "माफ़ कीजिए, अभी जवाब देने में समस्या आ रही है। कृपया दोबारा पूछें।"

st.title("✨ JUGNU AI Assistant")
st.caption("Aapka personal AI saathi — Superfast & Free")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]

# स्क्रीन पर पुराने मैसेज दिखाना
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
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
