import os
import io
import re
import base64
import sqlite3
import urllib.parse
import datetime
from io import BytesIO
from PIL import Image
import streamlit as st
from groq import Groq
from gtts import gTTS
from pypdf import PdfReader
from duckduckgo_search import DDGS

st.set_page_config(page_title="JUGNU AI - Super Assistant", page_icon="✨", layout="centered")

# --- UI Styling ---
st.markdown("""
<style>
footer {visibility: hidden;}

.stButton > button {
    font-size: 13px !important;
    padding: 6px 10px !important;
    border-radius: 12px !important;
    border: 1px solid #dcdcdc !important;
    background-color: #ffffff !important;
    color: #222222 !important;
    white-space: nowrap !important;
    width: 100% !important;
}
.stButton > button:hover {
    border-color: #ff4b4b !important;
    color: #ff4b4b !important;
}

div[data-testid="stAudioInput"] {
    max-width: 260px !important;
    margin: 0 auto !important;
}

.call-card {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    color: white;
    padding: 20px;
    border-radius: 18px;
    text-align: center;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
}

@media (max-width: 600px) {
    .block-container {
        padding: 1rem 0.5rem !important;
    }
}
</style>
""", unsafe_allow_html=True)

# --- SQLite Database ---
DB_FILE = "jugnu_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name TEXT,
            pin TEXT,
            plan_type TEXT DEFAULT 'free',
            msg_count INTEGER DEFAULT 0,
            last_msg_date TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            session_id TEXT PRIMARY KEY,
            username TEXT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            note TEXT,
            remind_time TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            memory_fact TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("INSERT OR IGNORE INTO users (username, name, pin, plan_type) VALUES ('arvind', 'अरविंद सिंह', '1234', 'vip')")
    cur.execute("INSERT OR IGNORE INTO users (username, name, pin, plan_type) VALUES ('admin', 'Admin', '0000', 'vip')")
    conn.commit()
    conn.close()

init_db()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(query, params)
    data = cur.fetchone() if fetchone else (cur.fetchall() if fetchall else None)
    if commit:
        conn.commit()
    conn.close()
    return data

# --- Persistent Login State ---
query_user = st.query_params.get("user", None)
if query_user and ("logged_in_user" not in st.session_state or not st.session_state.logged_in_user):
    user_row = db_query("SELECT username, name, plan_type FROM users WHERE username = ?", (query_user,), fetchone=True)
    if user_row:
        st.session_state.logged_in_user = user_row[0]
        st.session_state.logged_in_name = user_row[1]
        st.session_state.user_plan = user_row[2] if user_row[2] else "free"

if "app_lang" not in st.session_state:
    st.session_state.app_lang = "Hindi"
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = "arvind"
if "logged_in_name" not in st.session_state:
    st.session_state.logged_in_name = "अरविंद सिंह"
if "user_plan" not in st.session_state:
    st.session_state.user_plan = "vip"
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "राम राम अरविंद सिंह जी! मैं जुगनू हूँ। हुकम करो, आज कांई सेवा करूँ?"}]
if "uploaded_doc_text" not in st.session_state:
    st.session_state.uploaded_doc_text = ""
if "uploaded_image_base64" not in st.session_state:
    st.session_state.uploaded_image_base64 = None
if "call_mode_active" not in st.session_state:
    st.session_state.call_mode_active = False

st.query_params["user"] = st.session_state.logged_in_user
is_hi = (st.session_state.app_lang == "Hindi")
badge = "👑 VIP PRO" if st.session_state.user_plan == "vip" else "🆓 FREE"

# --- Sidebar Controls ---
st.sidebar.write(f"👤 **{st.session_state.logged_in_name}** ({badge})")
col_top1, col_top2 = st.sidebar.columns(2)
with col_top1:
    if st.button("➕ नई चैट", use_container_width=True):
        st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        st.session_state.messages = [{"role": "assistant", "content": f"राम राम {st.session_state.logged_in_name} जी! नई चैट शुरू हो गई है।"}]
        st.session_state.uploaded_doc_text = ""
        st.session_state.uploaded_image_base64 = None
        st.rerun()
with col_top2:
    if st.button("🚪 लॉगआउट", use_container_width=True):
        st.session_state.logged_in_user = None
        st.session_state.logged_in_name = None
        st.query_params.clear()
        st.session_state.messages = []
        st.rerun()

st.sidebar.markdown("---")

# Voice Call Toggle
call_btn_text = "🔴 कॉल समाप्त करें" if st.session_state.call_mode_active else "📞 वॉयस कॉल मोड"
if st.sidebar.button(call_btn_text, use_container_width=True):
    st.session_state.call_mode_active = not st.session_state.call_mode_active
    st.rerun()

# Earnings & VIP Dashboard
with st.sidebar.expander("💰 कमाई व VIP डैशबोर्ड", expanded=False):
    all_users = db_query("SELECT username, name, plan_type FROM users", fetchall=True)
    if all_users:
        st.caption(f"कुल सदस्य: {len(all_users)}")
        for u in all_users:
            st.write(f"• **{u[1]}** (`{u[0]}`) — {u[2].upper()}")
        target_u = st.selectbox("यूज़र चुनें:", [u[0] for u in all_users], key="monetize_u")
        new_plan = st.radio("प्लान बदलें:", ["free", "vip"], horizontal=True, key="monetize_p")
        if st.button("💾 सेव करें", use_container_width=True):
            db_query("UPDATE users SET plan_type = ? WHERE username = ?", (new_plan, target_u), commit=True)
            st.success("अपडेट हो गया!")
            st.rerun()

# Settings
with st.sidebar.expander("⚙️ सेटिंग्स (Settings)", expanded=False):
    chosen_lang = st.selectbox("🌐 भाषा (Language):", ["हिंदी (Hindi)", "English"], index=0 if is_hi else 1)
    new_lang = "Hindi" if "हिंदी" in chosen_lang else "English"
    if new_lang != st.session_state.app_lang:
        st.session_state.app_lang = new_lang
        st.rerun()
    bot_mode = st.selectbox("अंदाज़ (Mode):", ["मारवाड़ी / राजस्थानी", "दोस्ताना", "शिक्षक", "कहानीकार"])
    voice_speed = st.radio("आवाज़ की गति:", ["सामान्य", "धीमी"])
    is_slow_voice = (voice_speed == "धीमी")

# Memory Bank
with st.sidebar.expander("🧠 याददाश्त (Memory Bank)", expanded=False):
    mem_input = st.text_input("याद रखने की बात:", placeholder="उदा. मुझे चाय पसंद है")
    if st.button("💾 याद रखो", use_container_width=True) and mem_input.strip():
        db_query("INSERT INTO user_memories (username, memory_fact) VALUES (?, ?)", (st.session_state.logged_in_user, mem_input.strip()), commit=True)
        st.success("याद रख लिया!")
        st.rerun()
    user_mems = db_query("SELECT id, memory_fact FROM user_memories WHERE username = ?", (st.session_state.logged_in_user,), fetchall=True)
    if user_mems:
        for mid, mtext in user_mems:
            st.write(f"• {mtext}")
        if st.button("🗑 याददाश्त साफ़ करें", use_container_width=True):
            db_query("DELETE FROM user_memories WHERE username = ?", (st.session_state.logged_in_user,), commit=True)
            st.rerun()

# Smart Reminders & Diary
with st.sidebar.expander("⏰ स्मार्ट रिमाइंडर व डायरी", expanded=False):
    r_text = st.text_input("काम लिखें:", placeholder="उदा. 5 बजे मीटिंग है")
    r_time = st.time_input("समय चुनें:", value=datetime.time(17, 0))
    if st.button("⏰ रिमाइंडर सेट करें", use_container_width=True) and r_text.strip():
        db_query("INSERT INTO notes (username, note, remind_time) VALUES (?, ?, ?)", (st.session_state.logged_in_user, r_text.strip(), r_time.strftime("%H:%M")), commit=True)
        st.success("रिमाइंडर सेव!")
        st.rerun()
    user_notes = db_query("SELECT id, note, remind_time FROM notes WHERE username = ?", (st.session_state.logged_in_user,), fetchall=True)
    if user_notes:
        st.write("**शेड्यूल:**")
        for n_id, n_text, n_t in user_notes:
            st.write(f"• {n_text} ({n_t if n_t else 'नोट'})")
        if st.button("🗑 साफ़ करें", use_container_width=True):
            db_query("DELETE FROM notes WHERE username = ?", (st.session_state.logged_in_user,), commit=True)
            st.rerun()

# History & Search
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 चैट खोजें")
search_term = st.sidebar.text_input("ढूँढें...", placeholder="उदा. मौसम").strip().lower()
all_convos = db_query("SELECT session_id, title FROM conversations WHERE username = ? ORDER BY created_at DESC", (st.session_state.logged_in_user,), fetchall=True)
if all_convos:
    st.sidebar.markdown("💬 **पुरानी बातचीत (History):**")
    for s_id, s_title in all_convos:
        if search_term and search_term not in s_title.lower():
            continue
        if st.sidebar.button(f"📄 {s_title[:22]}", key=f"session_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            loaded_msgs = db_query("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (s_id,), fetchall=True)
            if loaded_msgs:
                st.session_state.messages = [{"role": r, "content": c} for r, c in loaded_msgs]
            st.rerun()

# --- Page Header ---
c1, c2 = st.columns([1, 4])
with c1:
    creator_img = None
    for fname in ["creater 1.jpg", "creater 1.png", "creator 1.jpg", "creator 1.png"]:
        if os.path.exists(fname):
            creator_img = fname
            break
    if creator_img:
        st.image(creator_img, width=80)
    else:
        st.write("👑")
with c2:
    st.subheader("✨ JUGNU AI")
    st.caption("निर्माता: अरविंद सिंह | पर्सनल स्मार्ट साथी")

st.divider()

# --- Backend Groq & Helper Functions ---
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def play_audio(text, autoplay=False, slow=False, lang="hi"):
    try:
        clean_text = text.split("http")[0].split("▶")[0].split("🔍")[0].strip()
        if not clean_text or clean_text.startswith("IMAGE_GEN:") or clean_text.startswith("त्रुटि:"):
            return
        sound = BytesIO()
        tts_lang = "hi" if lang == "Hindi" else "en"
        tts = gTTS(text=clean_text[:250], lang=tts_lang, slow=slow)
        tts.write_to_fp(sound)
        sound.seek(0)
        st.audio(sound, format="audio/mp3", autoplay=autoplay)
    except Exception:
        pass

def live_web_search(query):
    try:
        results = DDGS().text(query, max_results=3)
        if results:
            return "\n".join([f"• {r.get('title', '')}: {r.get('body', '')}" for r in results])
    except Exception:
        pass
    return ""

def get_jugnu_response(prompt_text, mode_name, lang="Hindi"):
    p = prompt_text.lower().strip()
    if any(k in p for k in ["kisne banaya", "creator kaun", "किसने बनाया"]):
        return "मुझे अरविंद सिंह ने बनाया है, जिनका गाँव दूजासर है और वर्तमान में श्री मोहनगढ़ में रहते हैं।"
    if any(k in p for k in ["marwadi", "मारवाड़ी"]) and any(k in p for k in ["bol", "aati", "sakte"]):
        return "हाँ भाई, म्हूँ मीठी मारवाड़ी बोल सकूँ हूँ! हुकम करो, आज कांई बात करनी है?"
    if any(k in p for k in ["photo", "फोटो", "तस्वीर"]) and any(a in p for a in ["banao", "बनाओ", "generate"]):
        query = p.replace("photo", "").replace("banao", "").replace("फोटो", "").replace("बनाओ", "").strip() or "Rajasthan royal desert fort"
        img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(query)}?width=800&height=500&nologo=true"
        return f"IMAGE_GEN:{img_url}|{query}"

    search_context = ""
    if any(k in p for k in ["live", "आज का", "ताजा", "खबर", "समाचार", "news", "भाव", "मंडी", "weather", "मौसम"]):
        search_context = live_web_search(prompt_text)

    mem_records = db_query("SELECT memory_fact FROM user_memories WHERE username = ?", (st.session_state.logged_in_user,), fetchall=True)
    memory_context = "\n".join([f"- {m[0]}" for m in mem_records]) if mem_records else ""

    if "मारवाड़ी" in mode_name or "marwadi" in p:
        sys_txt = f"थारो नाम जुगनू AI है। थानै अरविंद सिंह (गाँव दूजासर, श्री मोहनगढ़) बणायो है। यूजर को नाम {st.session_state.logged_in_name} है। थनै शुद्ध मीठी राजस्थानी/मारवाड़ी में 1-2 छोटा वाक्यों में आदर सूं जवाब देणो है।"
    elif lang == "Hindi":
        sys_txt = f"तुम जुगनू AI हो, जिसे अरविंद सिंह ने बनाया है। उपयोगकर्ता का नाम {st.session_state.logged_in_name} है। शुद्ध हिंदी में 1-2 छोटे वाक्यों में स्वाभाविक व सटीक उत्तर दो।"
    else:
        sys_txt = f"You are JUGNU AI, created by Arvind Singh. Respond naturally in 1-2 clear English sentences."

    if memory_context:
        sys_txt += f"\n\nयाददाश्त:\n{memory_context}"
    if st.session_state.uploaded_doc_text:
        sys_txt += f"\n\nफ़ाइल जानकारी:\n{st.session_state.uploaded_doc_text}"
    if search_context:
        sys_txt += f"\n\nसर्च जानकारी:\n{search_context}"

    for sm in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            res = client.chat.completions.create(
                model=sm,
                messages=[{"role": "system", "content": sys_txt}, {"role": "user", "content": prompt_text}],
                max_tokens=180,
                temperature=0.4
            )
            return res.choices[0].message.content.strip()
        except Exception:
            continue
    return "माफ़ी चाहता हूँ, कृपया 2 सेकंड बाद दोबारा पूछें।"

# Voice Call Screen Banner
if st.session_state.call_mode_active:
    st.markdown("""
        <div class="call-card">
            <h2>📞 जुगनू लाइव वॉयस कॉल एक्टिव है</h2>
            <p>नीचे माइक दबाकर बोलें, जुगनू सीधे आवाज़ में उत्तर देगा!</p>
        </div>
    """, unsafe_allow_html=True)

# Chat Message Stream
total_msgs = len(st.session_state.messages)
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        c = msg["content"]
        if c.startswith("IMAGE_GEN:"):
            parts = c.replace("IMAGE_GEN:", "").split("|")
            st.write(f"🎨 **जुगनू ने बनाई: {parts[1]}**")
            st.image(parts[0], use_container_width=True)
            st.markdown(f"[यहाँ क्लिक करके फोटो डाउनलोड करें]({parts[0]})")
        else:
            st.write(c)
            if msg["role"] == "assistant":
                auto_audio = True if st.session_state.call_mode_active else (i == total_msgs - 1 and total_msgs > 1)
                play_audio(c, autoplay=auto_audio, slow=is_slow_voice, lang=st.session_state.app_lang)

# 8 Quick Suggestion Buttons
if not st.session_state.call_mode_active:
    st.write("")
    st.caption("त्वरित सुझाव:")
    r1 = st.columns(4)
    r2 = st.columns(4)
    quick_prompt = None
    if r1[0].button("👑 निर्माता", use_container_width=True):
        quick_prompt = "tum ko kisne banaya ha unke bare me batao"
    if r1[1].button("⏰ समय", use_container_width=True):
        quick_prompt = "Abhi kya samay hua hai?"
    if r1[2].button("🌤 मौसम", use_container_width=True):
        quick_prompt = "Mohangarh me mausam kaisa hai?"
    if r1[3].button("😄 चुटकुला", use_container_width=True):
        quick_prompt = "Ek mazedaar chhota chutkula sunao"
    if r2[0].button("🎨 फोटो", use_container_width=True):
        quick_prompt = "photo banao Jaisalmer Fort"
    if r2[1].button("🎯 क्विज़", use_container_width=True):
        quick_prompt = "Mujhse Rajasthan se juda samanya gyan ka sawal poocho."
    if r2[2].button("🍎 सेहत", use_container_width=True):
        quick_prompt = "Aaj ke liye ek health tip batao."
    if r2[3].button("💬 मारवाड़ी", use_container_width=True):
        quick_prompt = "kya tum marwadi bol sakti ho"
else:
    quick_prompt = None

# Audio Mic Input
st.write("")
_, col_mic, _ = st.columns([1, 1, 1])
with col_mic:
    voice_input = st.audio_input("माइक", key="jugnu_mic_box", label_visibility="collapsed")

# File Upload Expand Box
if not st.session_state.call_mode_active:
    with st.expander("📎 फ़ाइल या फ़ोटो जोड़ें", expanded=False):
        uploaded_file = st.file_uploader("PDF, TXT या फ़ोटो चुनें:", type=["pdf", "txt", "png", "jpg", "jpeg"], key="main_chat_uploader")
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".pdf"):
                    st.session_state.uploaded_doc_text = "\n".join([page.extract_text() or "" for page in PdfReader(uploaded_file).pages])[:4000]
                    st.success(f"📄 '{uploaded_file.name}' जुड़ गई!")
                elif uploaded_file.name.endswith(".txt"):
                    st.session_state.uploaded_doc_text = uploaded_file.read().decode("utf-8")[:4000]
                    st.success(f"📄 '{uploaded_file.name}' जुड़ गई!")
                else:
                    st.image(uploaded_file, caption=uploaded_file.name, width=200)
                    st.success("🖼 फ़ोटो जुड़ गई!")
            except Exception as e:
                st.error(f"त्रुटि: {e}")

user_text = st.chat_input("यहाँ लिखकर, ऊपर माइक से या 📎 फ़ाइल जोड़कर पूछिए...")

def handle_user_query(query_text):
    if not st.session_state.current_session_id:
        st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    s_id = st.session_state.current_session_id
    if not db_query("SELECT session_id FROM conversations WHERE session_id = ?", (s_id,), fetchone=True):
        convo_title = query_text[:28] if len(query_text) <= 28 else query_text[:28] + "..."
        db_query("INSERT INTO conversations (session_id, username, title) VALUES (?, ?, ?)", (s_id, st.session_state.logged_in_user, convo_title), commit=True)
    st.session_state.messages.append({"role": "user", "content": query_text})
    db_query("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (s_id, "user", query_text), commit=True)
    with st.spinner("जुगनू सोच रहा है..."):
        reply = get_jugnu_response(query_text, bot_mode, st.session_state.app_lang)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    db_query("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (s_id, "assistant", reply), commit=True)
    st.rerun()

if quick_prompt:
    handle_user_query(quick_prompt)
elif voice_input is not None:
    audio_bytes = voice_input.getvalue()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != audio_bytes):
        st.session_state.last_voice = audio_bytes
        with st.spinner("आवाज़ सुनी जा रही है..."):
            recognized_text = ""
            try:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "recording.wav"
                transcription = client.audio.transcriptions.create(file=audio_file, model="whisper-large-v3-turbo", language="hi" if is_hi else "en")
                recognized_text = transcription.text.strip()
            except Exception as e:
                st.error(f"Voice error: {str(e)}")
        if recognized_text:
            handle_user_query(f"🎙 {recognized_text}")
elif user_text:
    handle_user_query(user_text)
