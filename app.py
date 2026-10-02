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

# --- Sidebar ---
is_hi = (st.session_state.app_lang == "Hindi")
badge = "👑 VIP PRO" if st.session_state.user_plan == "vip" else "🆓 FREE"

st.sidebar.write(f"👤 **{st.session_state.logged_in_name}** ({badge})")

if st.sidebar.button("➕ नई चैट (+ New Chat)", use_container_width=True):
    st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    st.session_state.messages = [{"role": "assistant", "content": f"राम राम {st.session_state.logged_in_name} जी! नई चैट तैयार है।"}]
    st.rerun()

st.sidebar.markdown("---")

# 1. File Upload / PDF Reader
with st.sidebar.expander("📄 फ़ाइल / PDF एनालिसिस", expanded=False):
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

# 2. Tone & Settings
with st.sidebar.expander("⚙️ सेटिंग्स और अंदाज़ (Settings)", expanded=True):
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

# 3. Smart Reminders & Notes
with st.sidebar.expander("⏰ स्मार्ट रिमाइंडर व डायरी", expanded=False):
    r_text = st.text_input("काम लिखें:", placeholder="उदा. 5 बजे काम है")
    r_time = st.time_input("समय चुनें:", value=datetime.time(17, 0))
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

# 4. Search Chat & History
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 चैट खोजें")
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
            return "\n".join([r.get("body", "") for r in results])
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
    if "मारवाड़ी" in mode_name or "marwadi" in p:
        sys_txt = (
            f"थारो नाम जुगनू AI है। थानै अरविंद सिंह (गाँव दूजासर, श्री मोहनगढ़) बणायो है। "
            f"यूजर को नाम {st.session_state.logged_in_name} है। "
            "थनै मीठी राजस्थानी/मारवाड़ी मिश्रित हिंदी में 1-2 छोटा वाक्यों में 'हाँ भाई, म्हूँ मारवाड़ी बोल सकूँ हूँ' कह कर बढ़िया जवाब देणो है।"
        )
    elif lang == "Hindi":
        sys_txt = f"तुम जुगनू AI हो, जिसे अरविंद सिंह ने बनाया है। उपयोगकर्ता का नाम {st.session_state.logged_in_name} है। शुद्ध हिंदी में 1-2 छोटे वाक्यों में स्वाभाविक उत्तर दो।"
    else:
        sys_txt = f"You are JUGNU AI, created by Arvind Singh. Respond naturally in 1-2 clear English sentences."

    if st.session_state.uploaded_doc_text:
        sys_txt += f"\n\nफ़ाइल जानकारी:\n{st.session_state.uploaded_doc_text}\nइसके आधार पर उत्तर दें।"

    if search_context:
        sys_txt += f"\n\nलाइव सर्च जानकारी:\n{search_context}\nइसके आधार पर उत्तर दें।"

    # Pure standard Groq Chat Model without dynamic detection bug
    try:
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
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

# Suggestion Buttons
st.write("")
st.caption("त्वरित सुझाव:")
r1 = st.columns(4)
r2 = st.columns(4)
quick_prompt = None

if r1[0].button("👑 निर्माता", use_container_width=True): quick_prompt = "tum ko kisne banaya ha unke bare me batao"
if r1[1].button("⏰ समय", use_container_width=True): quick_prompt = "Abhi kya samay hua hai?"
if r1[2].button("🌤 मौसम", use_container_width=True): quick_prompt = "Mohangarh me mausam kaisa hai?"
if r1[3].button("😄 चुटकुला", use_container_width=True): quick_prompt = "Ek mazedaar chhota chutkula sunao"

if r2[0].button("🎨 फोटो", use_container_width=True): quick_prompt = "photo banao Jaisalmer Fort"
if r2[1].button("🎯 क्विज़", use_container_width=True): quick_prompt = "Mujhse Rajasthan se juda samanya gyan ka sawal poocho."
if r2[2].button("🍎 सेहत", use_container_width=True): quick_prompt = "Aaj ke liye ek health tip batao."
if r2[3].button("📰 खबर", use_container_width=True): quick_prompt = "aaj ki taza khabar batao"

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
