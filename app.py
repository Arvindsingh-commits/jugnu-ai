import os
import io
import re
import datetime
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# --- Session States for Notes & Chat ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]
if "personal_notes" not in st.session_state:
    st.session_state.personal_notes = []

# --- Sidebar: Settings, Modes, Notepad & Export ---
st.sidebar.title("✨ JUGNU Settings")

# 1. Personality Mode
bot_mode = st.sidebar.selectbox(
    "JUGNU का अंदाज़ (Mode):",
    ["दोस्ताना (Friendly)", "शिक्षक (Study / Teacher)", "कहानीकार (Storyteller)"]
)

# 2. Voice Speed Control
voice_speed_option = st.sidebar.radio(
    "आवाज़ की गति (Voice Speed):",
    ["सामान्य (Normal)", "धीमी (Slow)"],
    index=0
)
is_slow_voice = (voice_speed_option == "धीमी (Slow)")

# 3. Personal Notepad / Reminders in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📝 जुगनू डायरी (Notes)")
new_note = st.sidebar.text_input("नया नोट / काम लिखें:", key="input_new_note", placeholder="उदा. 5 बजे बैंक जाना है")
if st.sidebar.button("➕ नोट जोड़ें", use_container_width=True):
    if new_note.strip():
        st.session_state.personal_notes.append(new_note.strip())
        st.sidebar.success("नोट सेव हो गया!")
        st.rerun()

if st.session_state.personal_notes:
    st.sidebar.write("**आपके सेव किए गए काम:**")
    for idx, note in enumerate(st.session_state.personal_notes):
        st.sidebar.markdown(f"{idx+1}. {note}")
    if st.sidebar.button("🗑️ सारे नोट साफ़ करें", use_container_width=True):
        st.session_state.personal_notes = []
        st.rerun()

st.sidebar.markdown("---")
# 4. Clear Chat Button
if st.sidebar.button("🗑️ पूरी चैट साफ़ करें", use_container_width=True):
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

# 100% Reliable Native Streamlit Audio Player
def play_audio(text, autoplay=False, slow=False):
    try:
        clean_text = text.split("```")[0].strip()
        clean_text = clean_text.split("http")[0].split("▶️")[0].split("🔍")[0].strip()
        if not clean_text:
            clean_text = "यहाँ आपका उत्तर है।"
        clean_text = clean_text[:250]
        
        sound = BytesIO()
        tts = gTTS(text=clean_text, lang="hi", slow=slow)
        tts.write_to_fp(sound)
        sound.seek(0)
        
        st.audio(sound, format="audio/mp3", autoplay=autoplay)
    except Exception as e:
        st.caption(f"Audio note: {str(e)}")

# Safe Math Evaluator
def try_evaluate_math(prompt_text):
    text = prompt_text.lower().replace("प्रतिशत", "%").replace("percent", "%")
    
    # 1. Percentage check: e.g. "550 ka 18%"
    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ka|का|of)\s*(\d+(?:\.\d+)?)\s*%", text)
    if not pct_match:
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:of|ka|का)?\s*(\d+(?:\.\d+)?)", text)
        if pct_match:
            pct_val = float(pct_match.group(1))
            num_val = float(pct_match.group(2))
            res = (num_val * pct_val) / 100.0
            return f"{num_val} का {pct_val}% बराबर {res:g} होगा।"
    else:
        num_val = float(pct_match.group(1))
        pct_val = float(pct_match.group(2))
        res = (num_val * pct_val) / 100.0
        return f"{num_val} का {pct_val}% बराबर {res:g} होगा।"

    # 2. Basic Arithmetic check
    clean = text.replace("गुना", "*").replace("गुणा", "*").replace("into", "*").replace("x", "*")
    clean = clean.replace("भाग", "/").replace("divide", "/").replace("बटा", "/")
    clean = clean.replace("जोड़", "+").replace("plus", "+").replace("धन", "+")
    clean = clean.replace("घटाव", "-").replace("minus", "-").replace("ऋण", "-")
    
    expr_match = re.search(r"(\d+(?:\.\d+)?\s*[\+\-\*\/]\s*\d+(?:\.\d+)?)", clean)
    if expr_match:
        try:
            expr = expr_match.group(1)
            ans = eval(expr, {"__builtins__": None}, {})
            return f"हिसाब के अनुसार उत्तर {ans:g} है।"
        except Exception:
            pass
    return None

def get_jugnu_response(prompt_text, mode_name):
    p = prompt_text.lower().strip()

    # Feature 1: Creator ke bare me poora parichay
    creator_keywords = [
        "bare me", "bare mein", "batao", "btao", "kutch batayo", "kuch batao",
        "kahan ke", "kahan rahte", "papa", "pita", "father", "village", "gaav", "gaon"
    ]
    if any(k in p for k in creator_keywords) and any(w in p for w in ["jisne", "jisne banaya", "banaya", "uske", "unke", "arvind", "creator", "nirmata"]):
        return "मुझे अरविंद सिंह ने बनाया है और उनके पापा का नाम मिस्टर रेवंत सिंह है और उनका गाँव दूजासर है और अभी श्री मोहनगढ़ में रहते हैं।"

    # Feature 2: Sirf pooche ki kisne banaya
    if any(k in p for k in ["kisne banaya", "kisne bnaya", "tumko kisne", "creator kaun", "creator kon", "किसने बनाया"]):
        return "मुझे अरविंद सिंह ने बनाया है।"

    # Feature 3: Personal Notes Reader
    if any(k in p for k in ["mere note", "mere notes", "kya kaam", "meri diary", "mera note", "नोट बताओ"]):
        if not st.session_state.personal_notes:
            return "आपकी डायरी में अभी कोई नोट सेव नहीं है। आप साइडबार में नया नोट जोड़ सकते हैं।"
        notes_str = "। ".join([f"{i+1}: {nt}" for i, nt in enumerate(st.session_state.personal_notes)])
        return f"आपकी डायरी में ये काम लिखे हैं: {notes_str}।"

    # Feature 4: Math & Calculation Engine
    math_ans = try_evaluate_math(prompt_text)
    if math_ans:
        return math_ans

    # Feature 5: Live Time & Date Tool (IST)
    if any(k in p for k in ["samay", "time", "kitne baje", "kya samay", "तारीख", "date", "दिन", "din", "समय"]):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        ist_now = now_utc + datetime.timedelta(hours=5, minutes=30)
        time_str = ist_now.strftime("%I:%M %p")
        date_str = ist_now.strftime("%d-%m-%Y")
        
        days_hindi = {
            "Monday": "सोमवार", "Tuesday": "मंगलवार", "Wednesday": "बुधवार",
            "Thursday": "गुरुवार", "Friday": "शुक्रवार", "Saturday": "शनिवार", "Sunday": "रविवार"
        }
        day_en = ist_now.strftime("%A")
        day_hi = days_hindi.get(day_en, day_en)

        if any(k in p for k in ["samay", "time", "kitne baje", "समय"]):
            return f"अभी समय {time_str} हुआ है।"
        return f"आज {day_hi} है और तारीख {date_str} है।"

    # Feature 6: Weather query
    if any(k in p for k in ["mausam", "weather", "taapman", "tapman", "मौसम"]):
        if any(w in p for w in ["mohangarh", "mohan garh", "मोहनगढ़"]):
            return "श्री मोहनगढ़ में मौसम धूप भरा और सुहावना है। दिन में हल्की गर्माहट और हवा चल रही है।"
        return "आज का मौसम साफ़ और सामान्य बना हुआ है।"

    # Mode Instructions
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

# Display Message History
total_msgs = len(st.session_state.messages)
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            play_audio(msg["content"], autoplay=(i == total_msgs - 1 and total_msgs > 1), slow=is_slow_voice)

# --- Export / Download Chat (Sidebar) ---
chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
st.sidebar.download_button(
    label="📥 बातचीत डाउनलोड करें",
    data=chat_text,
    file_name="jugnu_chat_history.txt",
    mime="text/plain",
    use_container_width=True
)

# --- Quick Suggestion Buttons ---
st.write("")
st.markdown("💡 **त्वरित सवाल (Quick Tap):**")
q_row1 = st.columns(4)
q_row2 = st.columns(4)
quick_prompt = None

if q_row1[0].button("👑 निर्माता कौन है?", use_container_width=True):
    quick_prompt = "tum ko jisne banaya ha unke bare me kutch batayo"
if q_row1[1].button("⏰ अभी क्या समय है?", use_container_width=True):
    quick_prompt = "Abhi kya samay hua hai?"
if q_row1[2].button("🌤️ मोहनगढ़ मौसम", use_container_width=True):
    quick_prompt = "Mohangarh me mausam kaisa hai?"
if q_row1[3].button("😄 एक चुटकुला", use_container_width=True):
    quick_prompt = "Ek mazedaar chhota chutkula sunao"

if q_row2[0].button("🎯 क्विज़ खेलें", use_container_width=True):
    quick_prompt = "Mujhse Rajasthan ya Bharat se juda ek rochak samanya gyan ka sawal poocho jisme 4 vikalp hon."
if q_row2[1].button("🍎 सेहत टिप", use_container_width=True):
    quick_prompt = "Aaj ke liye ek chhota aur faydemand health tip batao."
if q_row2[2].button("📝 मेरे नोट्स", use_container_width=True):
    quick_prompt = "mere notes batao"
if q_row2[3].button("📖 एक सुविचार", use_container_width=True):
    quick_prompt = "Aaj ka achha suvichar batao"

# --- Voice & Text Input ---
with st.container(border=True):
    st.markdown("🎙️ **JUGNU से बोलकर पूछने के लिए नीचे रिकॉर्ड करें:**")
    voice_input = st.audio_input("Record audio", key="jugnu_mic", label_visibility="collapsed")

user_text = st.chat_input("यहाँ लिखकर पूछिए...")

# Handle Query Trigger
def handle_user_query(query_text):
    st.session_state.messages.append({"role": "user", "content": query_text})
    with st.spinner("जुगनू सोच रहा है..."):
        reply = get_jugnu_response(query_text, bot_mode)
    
    # Smart Link Detection
    q_low = query_text.lower()
    if "youtube" in q_low:
        search_term = query_text.replace("youtube", "").replace("par", "").replace("khojo", "").strip()
        reply += f"\n\n▶️ [यहाँ क्लिक करके YouTube पर देखें](https://www.youtube.com/results?search_query={search_term})"
    elif "google" in q_low:
        search_term = query_text.replace("google", "").replace("par", "").replace("khojo", "").strip()
        reply += f"\n\n🔍 [यहाँ क्लिक करके Google पर खोजें](https://www.google.com/search?q={search_term})"

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
