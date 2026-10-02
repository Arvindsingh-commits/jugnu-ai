import os
import io
import base64
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# --- Sidebar: Controls, Modes & Clear Chat ---
st.sidebar.title("✨ JUGNU Settings")

# Personality Mode
bot_mode = st.sidebar.selectbox(
    "JUGNU ka Andaz (Mode):",
    ["दोस्ताना (Friendly)", "शिक्षक (Study / Teacher)", "कहानीकार (Storyteller)"]
)

# Clear Conversation
if st.sidebar.button("🗑️️ Chat Saaf Karein", use_container_width=True):
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]
    st.session_state.pop("last_voice", None)
    st.rerun()

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

# Auto-Playing Hindi Audio Player
def play_audio(text, autoplay=False):
    try:
        clean_text = text.split("```")[0].strip()
        if not clean_text:
            clean_text = "यहाँ आपका उत्तर है।"
        clean_text = clean_text[:250]
        
        sound = BytesIO()
        tts = gTTS(text=clean_text, lang="hi", slow=False)
        tts.write_to_fp(sound)
        sound.seek(0)
        
        b64_audio = base64.b64encode(sound.read()).decode("utf-8")
        auto_attr = "autoplay" if autoplay else ""
        audio_html = f"""
        
            
        
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    except Exception:
        pass

def get_jugnu_response(prompt_text, mode_name):
    p = prompt_text.lower().strip()

    # Rule 1: Creator ke bare me poora parichay
    creator_keywords = [
        "bare me", "bare mein", "batao", "btao", "kutch batayo", "kuch batao",
        "kahan ke", "kahan rahte", "papa", "pita", "father", "village", "gaav", "gaon"
    ]
    if any(k in p for k in creator_keywords) and any(w in p for w in ["jisne", "jisne banaya", "banaya", "uske", "unke", "arvind", "creator", "nirmata"]):
        return "मुझे अरविंद सिंह ने बनाया है और उनके पापा का नाम मिस्टर रेवंत सिंह है और उनका गाँव दूजासर है और अभी श्री मोहनगढ़ में रहते हैं।"

    # Rule 2: Kisne banaya
    if any(k in p for k in ["kisne banaya", "kisne bnaya", "tumko kisne", "creator kaun", "creator kon", "किसने बनाया"]):
        return "मुझे अरविंद सिंह ने बनाया है।"

    # Rule 3: Weather query
    if any(k in p for k in ["mausam", "weather", "taapman", "tapman", "मौसम"]):
        if any(w in p for w in ["mohangarh", "mohan garh", "मोहनगढ़"]):
            return "श्री मोहनगढ़ में मौसम धूप भरा और सुहावना है। दिन में हल्की गर्माहट और हवा चल रही है।"
        return "आज का मौसम साफ़ और सामान्य बना हुआ है।"

    # Mode based personality prompt
    mode_instructions = "तुम बहुत दोस्ताना और मददगार स्वभाव में बात करो।"
    if "शिक्षक" in mode_name:
        mode_instructions = "तुम एक बुद्धिमान शिक्षक की तरह ज्ञानवर्धक, सटीक और स्पष्ट भाषा में समझाओ।"
    elif "कहानीकार" in mode_name:
        mode_instructions = "तुम एक कहानीकार की तरह बहुत रोचक, मधुर और मनमोहक अंदाज़ में उत्तर दो।"

    system_prompt = (
        f"तुम जुगनू (JUGNU) हो, अरविंद सिंह द्वारा बनाए गए एक समझदार हिंदी AI सहायक। "
        f"{mode_instructions} "
        "तुम्हारा उत्तर केवल और केवल शुद्ध हिंदी (Devanagari script) में होना चाहिए। "
        "उत्तर 1 या 2 छोटे वाक्यों में स्वाभाविक तरीके से दो।"
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
                max_tokens=150,
                temperature=0.4
            )
            reply = completion.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as err:
            last_error = str(err)
            continue

    return f"Error: {last_error}" if last_error else "माफ़ कीजिए, कोई सक्रिय मॉडल नहीं मिला।"

# Session State for Messages
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]

# Display Message History
total_msgs = len(st.session_state.messages)
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            # Sirf sabse aakhiri naye response par auto-play hoga
            play_audio(msg["content"], autoplay=(i == total_msgs - 1 and total_msgs > 1))

# --- Quick Suggestion Buttons ---
st.write("")
st.markdown("💡 **त्वरित सवाल (Quick Tap):**")
q_cols = st.columns(4)
quick_prompt = None

if q_cols[0].button("👑 निर्माता कौन है?", use_container_width=True):
    quick_prompt = "tum ko jisne banaya ha unke bare me kutch batayo"
if q_cols[1].button("🌤️ मोहनगढ़ का मौसम?", use_container_width=True):
    quick_prompt = "Mohangarh me mausam kaisa hai?"
if q_cols[2].button("😄 एक चुटकुला सुनाओ", use_container_width=True):
    quick_prompt = "Ek mazedaar chhota chutkula sunao"
if q_cols[3].button("📖 एक सुविचार सुनाओ", use_container_width=True):
    quick_prompt = "Aaj ka achha suvichar batao"

# --- Voice & Text Input ---
with st.container(border=True):
    st.markdown("🎙️ **JUGNU से बोलकर पूछने के लिए नीचे रिकॉर्ड करें:**")
    voice_input = st.audio_input("Record audio", key="jugnu_mic", label_visibility="collapsed")

user_text = st.chat_input("यहाँ लिखकर पूछिए...")

# Common Trigger Function
def handle_user_query(query_text):
    st.session_state.messages.append({"role": "user", "content": query_text})
    with st.spinner("जुगनू सोच रहा है..."):
        reply = get_jugnu_response(query_text, bot_mode)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()

# 1. Quick suggestion button clicked
if quick_prompt:
    handle_user_query(quick_prompt)

# 2. Voice input received
elif voice_input is not None:
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
            handle_user_query(f"🎙 {recognized_text}")

# 3. Text input received
elif user_text:
    handle_user_query(user_text)
