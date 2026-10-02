import os
import io
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# --- Creator Profile Banner (अरविंद सिंह जी की नई फोटो और नाम) ---
col1, col2 = st.columns([1, 4])
with col1:
    creator_img = None
    # creator 1 और अन्य सभी नामों की जाँच
    possible_names = [
        "creator 1.jpg", "creator 1.png", "creator 1.jpeg", "creator 1.JPG", "creator 1.PNG",
        "creator1.jpg", "creator1.png", "creator1.jpeg", "creator1.JPG", "creator1.PNG",
        "creator.jpg", "creator.png", "creator.jpeg", "creator.JPG", "creator.PNG"
    ]
    for name in possible_names:
        if os.path.exists(name):
            creator_img = name
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

def play_audio(text):
    try:
        clean_text = text.split("```")[0].strip()
        if not clean_text:
            clean_text = "यहाँ आपका उत्तर है।"
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
        "नियम 1: अगर कोई पूछे कि तुम्हें किसने बनाया है या तुम्हारा निर्माता कौन है, तो साफ़ और गर्व से कहो: 'मुझे अरविंद सिंह ने बनाया है।' "
        "नियम 2: हमेशा केवल स्वाभाविक और सरल हिंदी या हिंग्लिश में 1 से 2 छोटे वाक्यों में उत्तर दो। "
        "नियम 3: अरबी या अन्य विदेशी भाषा बिल्कुल न बोलो।"
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

    return f"Error: {last_error}" if last_error else "माफ़ कीजिए, कोई सक्रिय मॉडल नहीं मिला।"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]

# चैट संदेश दिखाना
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"])

# माइक बॉक्स (Audio Input)
st.write("")
with st.container(border=True):
    st.markdown("🎙️ **JUGNU से बोलकर पूछने के लिए नीचे रिकॉर्ड करें:**")
    voice_input = st.audio_input("Record audio", key="jugnu_mic", label_visibility="collapsed")

# टेक्स्ट इनपुट
user_text = st.chat_input("यहाँ लिखकर पूछिए...")

# अगर आवाज़ से इनपुट आया हो
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

# अगर लिखकर इनपुट आया हो
elif user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("जुगनू सोच रहा है..."):
        reply = get_jugnu_response(user_text)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
