import os
import io
import re
import sqlite3
import urllib.parse
import datetime
from io import BytesIO
import streamlit as st
from groq import Groq
from gtts import gTTS
from pypdf import PdfReader
from duckduckgo_search import DDGS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# --- UI Styling ---
st.markdown("""

""", unsafe_allow_html=True)

# --- SQLite Database ---
DB_FILE = "jugnu_data.db"
DAILY_FREE_LIMIT = 15

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name TEXT,
            pin TEXT,
            plan_type TEXT DEFAULT 'free',
            msg_count INTEGER DEFAULT 0,
            last_msg_date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            session_id TEXT PRIMARY KEY,
            username TEXT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            note TEXT,
            remind_time TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO users (username, name, pin, plan_type) VALUES ('arvind', 'अरविंद सिंह', '1234', 'vip')")
    cursor.execute("INSERT OR IGNORE INTO users (username, name, pin, plan_type) VALUES ('admin', 'Admin', '0000', 'vip')")
    conn.commit()
    conn.close()

init_db()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(query, params)
    data = None
    if fetchone:
        data = cursor.fetchone()
    elif fetchall:
        data = cursor.fetchall()
    if commit:
        conn.commit()
    conn.close()
    return data

# --- Session States ---
if "app_lang" not in st.session_state:
    st.session_state.app_lang = "Hindi"
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None
if "logged_in_name" not in st.session_state:
    st.session_state.logged_in_name = None
if "user_plan" not in st.session_state:
    st.session_state.user_plan = "free"
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_doc_text" not in st.session_state:
    st.session_state.uploaded_doc_text = ""

# --- 1. Login Screen ---
if not st.session_state.logged_in_user:
    st.title("✨ JUGNU AI Assistant")
    selected_lang = st.radio("🌐 भाषा चुनें / Select Language:", ["हिंदी (Hindi)", "English"], horizontal=True)
    st.session_state.app_lang = "Hindi" if "हिंदी" in selected_lang else "English"
    is_hi = (st.session_state.app_lang == "Hindi")
    
    st.write("कृपया जुगनू का उपयोग करने के लिए लॉगिन करें" if is_hi else "Please log in to use JUGNU AI")
    tab_login, tab_signup = st.tabs(["लॉगिन (Login)" if is_hi else "Login", "नया खाता (Sign Up)" if is_hi else "Sign Up"])
    
    with tab_login:
        with st.form("login_form"):
            uname = st.text_input("यूज़रनेम (Username):" if is_hi else "Username:", placeholder="उदा. arvind").strip().lower()
            upin = st.text_input("पासवर्ड / PIN:" if is_hi else "Password / PIN:", type="password", placeholder="4 अंकों का पिन")
            submit_login = st.form_submit_button("लॉगिन करें" if is_hi else "Login", use_container_width=True)
            
            if submit_login:
                user = db_query("SELECT name, pin, plan_type FROM users WHERE username = ?", (uname,), fetchone=True)
                if user and user[1] == upin:
                    st.session_state.logged_in_user = uname
                    st.session_state.logged_in_name = user[0]
                    st.session_state.user_plan = user[2] if user[2] else "free"
                    st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    welcome_txt = f"राम राम {user[0]} जी! मैं जुगनू हूँ। आज आपरी कांई सेवा करूँ?" if is_hi else f"Hello {user[0]}! I am JUGNU AI. How can I help you today?"
                    st.session_state.messages = [{"role": "assistant", "content": welcome_txt}]
                    st.success("लॉगिन सफल रहा!" if is_hi else "Login successful!")
                    st.rerun()
                else:
                    st.error("ग़लत यूज़रनेम या पासवर्ड!" if is_hi else "Invalid username or password!")
    
    with tab_signup:
        with st.form("signup_form"):
            new_name = st.text_input("आपका पूरा नाम:" if is_hi else "Full Name:", placeholder="उदा. राहुल").strip()
            new_uname = st.text_input("नया यूज़रनेम चुनें:" if is_hi else "Choose Username:", placeholder="उदा. rahul123").strip().lower()
            new_pin = st.text_input("नया पासवर्ड / PIN बनाएँ:" if is_hi else "Create PIN:", type="password", placeholder="उदा. 5678")
            submit_signup = st.form_submit_button("खाता बनाएँ" if is_hi else "Create Account", use_container_width=True)
            
            if submit_signup:
                if not new_name or not new_uname or not new_pin:
                    st.warning("कृपया सभी विवरण भरें।" if is_hi else "Please fill all details.")
                else:
                    exists = db_query("SELECT username FROM users WHERE username = ?", (new_uname,), fetchone=True)
                    if exists:
                        st.error("यह यूज़रनेम पहले से मौजूद है।" if is_hi else "Username already exists.")
                    else:
                        today_str = datetime.date.today().isoformat()
                        db_query("INSERT INTO users (username, name, pin, plan_type, msg_count, last_msg_date) VALUES (?, ?, ?, 'free', 0, ?)", 
                                 (new_uname, new_name, new_pin, today_str), commit=True)
                        st.session_state.logged_in_user = new_uname
                        st.session_state.logged_in_name = new_name
                        st.session_state.user_plan = "free"
                        st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                        welcome_txt = f"राम राम {new_name} जी! आपका खाता बन गया है।" if is_hi else f"Hello {new_name}! Your account is ready."
                        st.session_state.messages = [{"role": "assistant", "content": welcome_txt}]
                        st.success("खाता सफलतापूर्वक बन गया!" if is_hi else "Account created successfully!")
                        st.rerun()
    st.stop()

# --- 2. Main Dashboard ---
is_hi = (st.session_state.app_lang == "Hindi")

badge = "👑 VIP PRO" if st.session_state.user_plan == "vip" else "🆓 FREE"
st.sidebar.write(f"👤 **{st.session_state.logged_in_name}** ({badge})")

if st.sidebar.button("🚪 लॉगआउट (Logout)" if is_hi else "🚪 Logout", use_container_width=True):
    st.session_state.logged_in_user = None
    st.session_state.logged_in_name = None
    st.session_state.current_session_id = None
    st.session_state.messages = []
    st.rerun()

if st.sidebar.button("➕ नई चैट (+ New Chat)" if is_hi else "➕ New Chat", use_container_width=True):
    st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    welcome_text = f"राम राम {st.session_state.logged_in_name} जी! नई चैट तैयार है।" if is_hi else f"Hello {st.session_state.logged_in_name}! New chat started."
    st.session_state.messages = [{"role": "assistant", "content": welcome_text}]
    st.rerun()

st.sidebar.markdown("---")

# File & Document Analysis (PDF / TXT)
with st.sidebar.expander("📄 फ़ाइल / PDF एनालिसिस" if is_hi else "📄 Document Analysis", expanded=False):
    uploaded_file = st.file_uploader("PDF या TXT अपलोड करें", type=["pdf", "txt"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".pdf"):
                reader = PdfReader(uploaded_file)
                text = "\n".join([page.extract_text() or "" for page in reader.pages])
            else:
                text = uploaded_file.read().decode("utf-8")
            st.session_state.uploaded_doc_text = text[:4000]
            st.success("फ़ाइल लोड हो गई! अब इससे जुड़े सवाल पूछें।")
        except Exception as e:
            st.error(f"फ़ाइल पढ़ने में त्रुटि: {e}")

# Settings & Tone
with st.sidebar.expander("⚙️ सेटिंग्स और अंदाज़ (Persona)" if is_hi else "⚙️ Settings & Tone", expanded=False):
    chosen_lang = st.selectbox("🌐 भाषा (Language):", ["हिंदी (Hindi)", "English"], index=0 if is_hi else 1)
    new_lang = "Hindi" if "हिंदी" in chosen_lang else "English"
    if new_lang != st.session_state.app_lang:
        st.session_state.app_lang = new_lang
        st.rerun()

    bot_mode = st.selectbox(
        "अंदाज़ (Persona):", 
        ["मारवाड़ी / राजस्थानी (देसी)", "दोस्ताना (Friendly)", "शिक्षक (Teacher)", "कहानीकार (Storyteller)"]
    )
    voice_speed = st.radio("आवाज़ की गति:", ["सामान्य", "धीमी"])
    is_slow_voice = (voice_speed == "धीमी")

# Smart Reminders & Diary
with st.sidebar.expander("⏰ स्मार्ट रिमाइंडर व डायरी" if is_hi else "⏰ Reminders & Notes", expanded=False):
    r_text = st.text_input("काम लिखें:", placeholder="उदा. शाम 6 बजे मीटिंग")
    r_time = st.time_input("समय चुनें:", value=datetime.time(18, 0))
    if st.button("⏰ रिमाइंडर सेट करें", use_container_width=True):
        if r_text.strip():
            db_query("INSERT INTO notes (username, note, remind_time) VALUES (?, ?, ?)", 
                     (st.session_state.logged_in_user, r_text.strip(), r_time.strftime("%H:%M")), commit=True)
            st.success("रिमाइंडर सेव हो गया!")
            st.rerun()

    user_notes = db_query("SELECT id, note, remind_time FROM notes WHERE username = ?", (st.session_state.logged_in_user,), fetchall=True)
    if user_notes:
        st.write("**आपके शेड्यूल:**")
        for n_id, n_text, n_t in user_notes:
            st.write(f"• {n_text} ({n_t if n_t else 'नोट'})")
        if st.button("🗑 सारे साफ़ करें", use_container_width=True):
            db_query("DELETE FROM notes WHERE username = ?", (st.session_state.logged_in_user,), commit=True)
            st.rerun()

# Search Chat & History
st.sidebar.subheader("🔍 चैट खोजें" if is_hi else "🔍 Search Chat")
search_term = st.sidebar.text_input("ढूँढें...", placeholder="उदा. मौसम, सवाल").strip().lower()
all_convos = db_query("SELECT session_id, title FROM conversations WHERE username = ? ORDER BY created_at DESC", (st.session_state.logged_in_user,), fetchall=True)

if all_convos:
    for s_id, s_title in all_convos:
        if search_term and search_term not in s_title.lower():
            continue
        if st.sidebar.button(f"📄 {s_title[:22]}", key=f"session_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            loaded_msgs = db_query("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (s_id,), fetchall=True)
            if loaded_msgs:
                st.session_state.messages = [{"role": r, "content": c} for r, c in loaded_msgs]
            st.rerun()

# Creator Banner
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

# Backend API Setup
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def play_audio(text, autoplay=False, slow=False, lang="hi"):
    try:
        clean_text = text.split("http")[0].split("▶")[0].split("🔍")[0].strip()
        if not clean_text or clean_text.startswith("IMAGE_GEN:"):
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
            snippet = "\n".join([r.get("body", "") for r in results])
            return snippet
    except Exception:
        pass
    return ""

def get_jugnu_response(prompt_text, mode_name, lang="Hindi"):
    p = prompt_text.lower().strip()

    # Image gen trigger
    if any(k in p for k in ["photo", "फोटो", "तस्वीर", "tasveer", "image"]) and any(a in p for a in ["banao", "बनाओ", "dikhao", "generate"]):
        query = p.replace("photo", "").replace("banao", "").replace("फोटो", "").replace("बनाओ", "").strip()
        if not query:
            query = "Rajasthan royal heritage culture"
        img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(query)}?width=800&height=500&nologo=true"
        return f"IMAGE_GEN:{img_url}|{query}"

    # Live Search Trigger
    search_context = ""
    if any(k in p for k in ["live", "आज का", "ताजा", "खबर", "समाचार", "news", "भाव", "मंडी"]):
        search_context = live_web_search(prompt_text)

    # Tone Setup
    if "मारवाड़ी" in mode_name:
        sys_txt = (
            f"थारो नाम जुगनू AI है। थानै अरविंद सिंह (गाँव दूजासर, श्री मोहनगढ़) बणायो है। "
            f"यूजर को नाम {st.session_state.logged_in_name} है। "
            "थनै मीठी राजस्थानी/मारवाड़ी मिश्रित हिंदी में 1-2 छोटा वाक्यों में बढ़िया जवाब देणो है।"
        )
    elif lang == "Hindi":
        sys_txt = f"तुम जुगनू AI हो, जिसे अरविंद सिंह ने बनाया है। उपयोगकर्ता का नाम {st.session_state.logged_in_name} है। शुद्ध हिंदी में 1-2 छोटे वाक्यों में स्वाभाविक उत्तर दो।"
    else:
        sys_txt = f"You are JUGNU AI, created by Arvind Singh. Respond naturally in 1-2 clear English sentences."

    if st.session_state.uploaded_doc_text:
        sys_txt += f"\n\nअपलोड की गई फ़ाइल की जानकारी:\n{st.session_state.uploaded_doc_text}\nउपयोगकर्ता के सवाल का जवाब इसी फ़ाइल के आधार पर दें।"

    if search_context:
        sys_txt += f"\n\nइंटरनेट से ताज़ा सर्च जानकारी:\n{search_context}\nताज़ा जानकारी के आधार पर उत्तर दें।"

    available_model_ids = []
    try:
        models_data = client.models.list()
        available_model_ids = [m.id for m in models_data.data]
    except Exception:
        pass

    preferred_models = ["llama-3.1-8b-instant", "llama3-8b-8192", "mixtral-8x7b-32768"]
    model_to_use = "llama-3.1-8b-instant"
    for pm in preferred_models:
        if pm in available_model_ids:
            model_to_use = pm
            break

    try:
        res = client.chat.completions.create(
            model=model_to_use,
            messages=[{"role": "system", "content": sys_txt}, {"role": "user", "content": prompt_text}],
            max_tokens=150,
            temperature=0.4
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"त्रुटि: {str(e)}"

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
                play_audio(c, autoplay=(i == total_msgs - 1 and total_msgs > 1), slow=is_slow_voice, lang=st.session_state.app_lang)

# Mic and Chat Input
st.write("")
_, col_mic, _ = st.columns([1, 1, 1])
with col_mic:
    voice_input = st.audio_input("माइक", key="jugnu_mic_box", label_visibility="collapsed")

user_text = st.chat_input("यहाँ लिखकर, माइक से या फ़ाइल अपलोड करके पूछिए...")

def handle_user_query(query_text):
    if not st.session_state.current_session_id:
        st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    s_id = st.session_state.current_session_id

    exists_convo = db_query("SELECT session_id FROM conversations WHERE session_id = ?", (s_id,), fetchone=True)
    if not exists_convo:
        convo_title = query_text[:28] if len(query_text) <= 28 else query_text[:28] + "..."
        db_query("INSERT INTO conversations (session_id, username, title) VALUES (?, ?, ?)", 
                 (s_id, st.session_state.logged_in_user, convo_title), commit=True)

    st.session_state.messages.append({"role": "user", "content": query_text})
    db_query("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
             (s_id, "user", query_text), commit=True)
    
    with st.spinner("जुगनू काम कर रहा है..."):
        reply = get_jugnu_response(query_text, bot_mode, st.session_state.app_lang)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    db_query("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
             (s_id, "assistant", reply), commit=True)
    st.rerun()

if voice_input is not None:
    audio_bytes = voice_input.getvalue()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != audio_bytes):
        st.session_state.last_voice = audio_bytes
        with st.spinner("आवाज़ सुनी जा रही है..."):
            recognized_text = ""
            try:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "recording.wav"
                transcription = client.audio.transcriptions.create(
                    file=audio_file, 
                    model="whisper-large-v3-turbo", 
                    language="hi" if is_hi else "en"
                )
                recognized_text = transcription.text.strip()
            except Exception as e:
                st.error(f"Voice error: {str(e)}")
        if recognized_text:
            handle_user_query(f"🎙 {recognized_text}")
elif user_text:
    handle_user_query(user_text)
