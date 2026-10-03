import os
import re
import io
import json
import time
import hashlib
import sqlite3
from datetime import datetime

import streamlit as st
from groq import Groq
from gtts import gTTS
from pypdf import PdfReader
from PIL import Image

try:
    from ddgs import DDGS
except Exception:
    try:
        from duckduckgo_search import DDGS
    except Exception:
        DDGS = None

APP_NAME = "जुगनू AI"
DB_FILE = "jugnu_data.db"
DEFAULT_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"
WHISPER_MODEL = "whisper-large-v3-turbo"

st.set_page_config(
    page_title="जुगनू AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

def clean_text(text):
    if text is None:
        return ""
    text = str(text)
    for ch in ("\u00a0", "\u2007", "\u202f"):
        text = text.replace(ch, " ")
    return re.sub(r"[ \t]+", " ", text).strip()

def db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name TEXT,
            plan TEXT DEFAULT 'FREE',
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            task TEXT,
            remind_at TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            memory TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            username TEXT PRIMARY KEY,
            language TEXT DEFAULT 'Hindi',
            bot_mode TEXT DEFAULT 'दोस्ताना',
            voice_speed TEXT DEFAULT 'सामान्य'
        )
    """)
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT OR IGNORE INTO users(username,name,plan,created_at) VALUES(?,?,?,?)",
        ("arvind", "अरविंद सिंह", "VIP PRO", now)
    )
    cur.execute(
        "INSERT OR IGNORE INTO app_settings(username) VALUES(?)",
        ("arvind",)
    )
    conn.commit()
    conn.close()

init_db()

if "username" not in st.session_state:
    st.session_state.username = st.query_params.get("user", "arvind") or "arvind"
st.query_params["user"] = st.session_state.username

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "file_text" not in st.session_state:
    st.session_state.file_text = ""
if "file_name" not in st.session_state:
    st.session_state.file_name = ""
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = ""
if "tts_cache" not in st.session_state:
    st.session_state.tts_cache = {}
if "quick_prompt" not in st.session_state:
    st.session_state.quick_prompt = ""
if "web_search" not in st.session_state:
    st.session_state.web_search = False
if "pdf_mode" not in st.session_state:
    st.session_state.pdf_mode = True
if "voice_call" not in st.session_state:
    st.session_state.voice_call = False
if "auto_speak" not in st.session_state:
    st.session_state.auto_speak = False

def current_user():
    conn = db()
    row = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (st.session_state.username,)
    ).fetchone()
    conn.close()
    return row

def load_settings():
    conn = db()
    row = conn.execute(
        "SELECT * FROM app_settings WHERE username=?",
        (st.session_state.username,)
    ).fetchone()
    conn.close()
    return row

def save_setting(column, value):
    if column not in {"language", "bot_mode", "voice_speed"}:
        return
    conn = db()
    conn.execute(
        f"UPDATE app_settings SET {column}=? WHERE username=?",
        (value, st.session_state.username)
    )
    conn.commit()
    conn.close()

def create_conversation(title="नई चैट"):
    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations(username,title,created_at,updated_at) VALUES(?,?,?,?)",
        (st.session_state.username, clean_text(title)[:80] or "नई चैट", now, now)
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    st.session_state.conversation_id = cid
    st.session_state.messages = []
    return cid

def ensure_conversation(title="नई चैट"):
    if not st.session_state.conversation_id:
        return create_conversation(title)
    return st.session_state.conversation_id

def save_message(role, content):
    cid = ensure_conversation(content[:60] if role == "user" else "नई चैट")
    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    conn.execute(
        "INSERT INTO messages(conversation_id,role,content,created_at) VALUES(?,?,?,?)",
        (cid, role, content, now)
    )
    conn.execute(
        "UPDATE conversations SET updated_at=? WHERE id=?",
        (now, cid)
    )
    conn.commit()
    conn.close()

def load_conversation(cid):
    conn = db()
    rows = conn.execute(
        "SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id",
        (cid,)
    ).fetchall()
    conv = conn.execute(
        "SELECT title FROM conversations WHERE id=?",
        (cid,)
    ).fetchone()
    conn.close()
    st.session_state.conversation_id = cid
    st.session_state.messages = [{"role": r["role"], "content": r["content"]} for r in rows]
    return conv["title"] if conv else "पुरानी चैट"

def get_conversations(search=""):
    conn = db()
    if search:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE username=? AND title LIKE ? ORDER BY updated_at DESC LIMIT 50",
            (st.session_state.username, f"%{search}%")
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE username=? ORDER BY updated_at DESC LIMIT 50",
            (st.session_state.username,)
        ).fetchall()
    conn.close()
    return rows

def get_memories():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM user_memories WHERE username=? ORDER BY id DESC",
        (st.session_state.username,)
    ).fetchall()
    conn.close()
    return rows

def add_memory(memory):
    memory = clean_text(memory)
    if not memory:
        return
    conn = db()
    conn.execute(
        "INSERT INTO user_memories(username,memory,created_at) VALUES(?,?,?)",
        (st.session_state.username, memory, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

def delete_memory(mid):
    conn = db()
    conn.execute(
        "DELETE FROM user_memories WHERE id=? AND username=?",
        (mid, st.session_state.username)
    )
    conn.commit()
    conn.close()

def get_notes():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM notes WHERE username=? ORDER BY remind_at ASC, id DESC",
        (st.session_state.username,)
    ).fetchall()
    conn.close()
    return rows

def add_note(task, remind_at):
    if not clean_text(task):
        return
    conn = db()
    conn.execute(
        "INSERT INTO notes(username,task,remind_at,created_at) VALUES(?,?,?,?)",
        (
            st.session_state.username,
            clean_text(task),
            clean_text(remind_at),
            datetime.now().isoformat(timespec="seconds")
        )
    )
    conn.commit()
    conn.close()

def delete_note(nid):
    conn = db()
    conn.execute(
        "DELETE FROM notes WHERE id=? AND username=?",
        (nid, st.session_state.username)
    )
    conn.commit()
    conn.close()

def get_api_key():
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY", "")

def groq_client():
    key = get_api_key()
    if not key:
        return None
    return Groq(api_key=key)

def transcribe_audio(audio_file):
    client = groq_client()
    if client is None:
        return "", "GROQ_API_KEY नहीं मिला। Streamlit Secrets में GROQ_API_KEY डालें।"
    try:
        audio_file.seek(0)
        result = client.audio.transcriptions.create(
            file=("voice.wav", audio_file.read()),
            model=WHISPER_MODEL,
            response_format="text"
        )
        return clean_text(result), ""
    except Exception as e:
        return "", f"Voice transcription error: {e}"

def speak(text):
    text = clean_text(text)
    if not text:
        return None
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if key in st.session_state.tts_cache:
        return st.session_state.tts_cache[key]
    try:
        lang = "hi"
        if re.search(r"[A-Za-z]", text) and not re.search(r"[\u0900-\u097F]", text):
            lang = "en"
        slow = load_settings()["voice_speed"] == "धीमी"
        audio = io.BytesIO()
        gTTS(text=text[:4000], lang=lang, slow=slow).write_to_fp(audio)
        audio.seek(0)
        data = audio.getvalue()
        st.session_state.tts_cache[key] = data
        return data
    except Exception:
        return None

def extract_document(uploaded):
    if uploaded is None:
        return "", ""
    name = uploaded.name
    try:
        raw = uploaded.getvalue()
        if name.lower().endswith(".txt"):
            return clean_text(raw.decode("utf-8", errors="ignore")), name
        if name.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(raw))
            parts = []
            for i, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                if txt.strip():
                    parts.append(f"[Page {i+1}]\n{txt}")
            return clean_text("\n\n".join(parts)), name
    except Exception as e:
        return f"Document read error: {e}", name
    return "", name

def search_web(query, max_results=5):
    if DDGS is None:
        return []
    try:
        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": clean_text(item.get("title", "")),
                    "url": item.get("href") or item.get("url") or "",
                    "body": clean_text(item.get("body", ""))
                })
        return results
    except Exception:
        return []

def search_context(results):
    if not results:
        return ""
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"SOURCE {i}\nTitle: {r['title']}\nURL: {r['url']}\nSummary: {r['body']}"
        )
    return "\n\n".join(blocks)

def likely_needs_search(text):
    words = [
        "आज", "अभी", "लेटेस्ट", "न्यूज़", "समाचार", "मौसम", "तापमान",
        "weather", "today", "latest", "news", "current", "price", "भाव",
        "रेट", "result", "परिणाम", "कब", "कितना", "2026"
    ]
    t = text.lower()
    return any(w.lower() in t for w in words)

def build_system_prompt(settings, memories):
    mode = settings["bot_mode"] if settings else "दोस्ताना"
    lang = settings["language"] if settings else "Hindi"
    mode_text = {
        "दोस्ताना": "दोस्त की तरह सरल, गर्मजोशी भरा और सीधा जवाब दो।",
        "शिक्षक": "शिक्षक की तरह step-by-step, साफ और परीक्षा उपयोगी जवाब दो।",
        "कहानीकार": "जहाँ उपयुक्त हो वहाँ रोचक कहानी जैसे उदाहरण दो।",
        "मारवाड़ी / राजस्थानी": "सरल, प्राकृतिक मारवाड़ी/राजस्थानी में जवाब दो।"
    }.get(mode, "सरल और दोस्ताना जवाब दो।")
    memory_text = "\n".join(f"- {m['memory']}" for m in memories[-20:])
    return f"""
तुम जुगनू AI हो, अरविंद सिंह के personal smart companion हो।
भाषा preference: {lang}
Bot mode: {mode_text}
अरविंद के बारे में उपलब्ध memory:
{memory_text if memory_text else "- अभी कोई memory नहीं है।"}

नियम:
- तथ्य नहीं गढ़ना।
- यदि live/current जानकारी चाहिए और web context दिया गया है तो उसी को प्राथमिकता दो।
- web context में स्रोत हों तो उत्तर के अंत में छोटे 'स्रोत' सेक्शन में URLs दो।
- PDF/document context दिया हो तो उसी के आधार पर जवाब दो और page number बताओ जहाँ संभव हो।
- जवाब उपयोगी और सीधे रखो।
- बहुत लंबा उत्तर तभी दो जब user मांगे।
"""

def call_llm(user_text, document_text="", web_results=None):
    client = groq_client()
    if client is None:
        return "GROQ_API_KEY नहीं मिला। Streamlit Secrets में GROQ_API_KEY डालें।"

    settings = load_settings()
    memories = get_memories()
    system = build_system_prompt(settings, memories)

    context_parts = []
    if document_text:
        doc = document_text[:30000]
        context_parts.append("DOCUMENT CONTEXT:\n" + doc)
    if web_results:
        context_parts.append("LIVE WEB SEARCH CONTEXT:\n" + search_context(web_results))

    user_content = clean_text(user_text)
    if context_parts:
        user_content += "\n\n" + "\n\n".join(context_parts)

    messages = [{"role": "system", "content": system}]
    for m in st.session_state.messages[-12:]:
        messages.append({
            "role": m["role"],
            "content": clean_text(m["content"])[:12000]
        })
    messages.append({"role": "user", "content": user_content})

    for model in (DEFAULT_MODEL, FALLBACK_MODEL):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
                max_tokens=1800
            )
            return clean_text(response.choices[0].message.content)
        except Exception as e:
            last_error = str(e)
            continue
    return f"AI error: {last_error}"

def creator_answer(text):
    if "निर्माता" in text.lower() or "creator" in text.lower() or "किसने बनाया" in text.lower():
        return "जुगनू AI के निर्माता अरविंद सिंह हैं। उनका संबंध गाँव दूजासर, श्री मोहनगढ़ से है।"
    return None

def photo_request(text):
    t = text.lower()
    keys = [
        "photo बनाओ", "फोटो बनाओ", "image बनाओ", "इमेज बनाओ",
        "चित्र बनाओ", "तस्वीर बनाओ", "generate image", "generate photo",
        "make an image", "create image"
    ]
    return any(k in t for k in keys)

def image_placeholder_message(prompt):
    return (
        "🎨 Image Generation अभी इस version में external API key के बिना "
        "सक्रिय नहीं है। Pollinations की current API में generation requests "
        "के लिए API key आवश्यक है, इसलिए मैंने कोई hidden/unsafe key नहीं जोड़ी है। "
        "बाकी Jugnu AI features चालू हैं।"
    )

def render_message(i, m):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            audio = speak(m["content"])
            if audio:
                if st.button("🔊 सुनें", key=f"listen_{i}"):
                    st.audio(audio, format="audio/mp3", autoplay=False)

def process_prompt(prompt, document_text=""):
    prompt = clean_text(prompt)
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message("user", prompt)

    creator = creator_answer(prompt)
    if creator:
        answer = creator
        results = []
    elif photo_request(prompt):
        answer = image_placeholder_message(prompt)
        results = []
    else:
        do_search = st.session_state.web_search or likely_needs_search(prompt)
        results = search_web(prompt) if do_search else []
        use_doc = bool(document_text) and st.session_state.pdf_mode
        answer = call_llm(prompt, document_text if use_doc else "", results)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    save_message("assistant", answer)

    if st.session_state.voice_call or st.session_state.auto_speak:
        audio = speak(answer)
        if audio:
            st.session_state.pending_audio = audio

def quick_buttons():
    cols = st.columns(8)
    items = [
        ("👑 निर्माता", "जुगनू AI का निर्माता कौन है?"),
        ("⏰ समय", "अभी का सही समय बताओ।"),
        ("🌤 मौसम", "आज का मौसम और तापमान बताओ।"),
        ("😄 चुटकुला", "एक मजेदार हिंदी चुटकुला सुनाओ।"),
        ("🎨 फोटो", "राजस्थान के रेगिस्तान की cinematic photo बनाओ।"),
        ("🎯 क्विज़", "मुझे सामान्य ज्ञान का एक quiz question दो।"),
        ("🍎 सेहत", "आज के लिए एक सामान्य healthy habit बताओ।"),
        ("💬 मारवाड़ी", "मारवाड़ी में मुझसे बात करो।")
    ]
    for col, (label, prompt) in zip(cols, items):
        with col:
            if st.button(label, use_container_width=True):
                st.session_state.quick_prompt = prompt
                st.rerun()

user = current_user()
settings = load_settings()

with st.sidebar:
    st.markdown("## ✨ जुगनू AI")
    st.markdown(f"**👤 {user['name']} (👑 {user['plan']})**")

    if st.button("➕ नई चैट", use_container_width=True):
        create_conversation()
        st.rerun()

    st.toggle("📞 Voice Call Mode", key="voice_call")
    st.toggle("🔊 Auto Speak", key="auto_speak")
    st.toggle("🌐 Web Search", key="web_search")
    st.toggle("📄 PDF Context Mode", key="pdf_mode")

    st.divider()

    with st.expander("⚙️ Settings", expanded=False):
        language = st.selectbox(
            "भाषा",
            ["Hindi", "English", "Hindi + English"],
            index=["Hindi", "English", "Hindi + English"].index(settings["language"])
            if settings and settings["language"] in ["Hindi", "English", "Hindi + English"] else 0
        )
        bot_mode = st.selectbox(
            "Bot Mode",
            ["दोस्ताना", "शिक्षक", "कहानीकार", "मारवाड़ी / राजस्थानी"],
            index=["दोस्ताना", "शिक्षक", "कहानीकार", "मारवाड़ी / राजस्थानी"].index(settings["bot_mode"])
            if settings and settings["bot_mode"] in ["दोस्ताना", "शिक्षक", "कहानीकार", "मारवाड़ी / राजस्थानी"] else 0
        )
        voice_speed = st.selectbox(
            "Voice Speed",
            ["सामान्य", "धीमी"],
            index=["सामान्य", "धीमी"].index(settings["voice_speed"])
            if settings and settings["voice_speed"] in ["सामान्य", "धीमी"] else 0
        )
        if st.button("💾 Settings Save"):
            save_setting("language", language)
            save_setting("bot_mode", bot_mode)
            save_setting("voice_speed", voice_speed)
            st.success("Settings saved")

    with st.expander("🧠 Memory Bank", expanded=False):
        mem_text = st.text_input("नई memory")
        if st.button("➕ Memory Save") and mem_text.strip():
            add_memory(mem_text)
            st.success("Memory saved")
            st.rerun()
        for mem in get_memories()[:15]:
            c1, c2 = st.columns([5, 1])
            c1.write("• " + mem["memory"])
            if c2.button("🗑️", key=f"mem_{mem['id']}"):
                delete_memory(mem["id"])
                st.rerun()

    with st.expander("⏰ Smart Reminder / Diary", expanded=False):
        task = st.text_input("Task")
        remind = st.text_input("Time / Date", placeholder="जैसे 2026-10-05 18:00")
        if st.button("➕ Save Reminder"):
            add_note(task, remind)
            st.success("Reminder saved")
            st.rerun()
        for note in get_notes()[:10]:
            c1, c2 = st.columns([5, 1])
            c1.write(f"⏰ {note['task']}\n\n{note['remind_at']}")
            if c2.button("🗑️", key=f"note_{note['id']}"):
                delete_note(note["id"])
                st.rerun()

    with st.expander("🔎 Chat Search / History", expanded=False):
        search = st.text_input("Chat search")
        for conv in get_conversations(search)[:20]:
            title = conv["title"] or "नई चैट"
            if st.button(title[:40], key=f"conv_{conv['id']}", use_container_width=True):
                load_conversation(conv["id"])
                st.rerun()

    with st.expander("👑 VIP Dashboard", expanded=False):
        st.metric("Current Plan", user["plan"])
        st.write("VIP PRO features: Voice, Memory, PDF, Web Search और advanced chat.")
        st.info("Payment system अभी अलग से integrate करना होगा।")

    st.divider()
    if st.button("🚪 लॉगआउट", use_container_width=True):
        st.session_state.username = "arvind"
        st.query_params["user"] = "arvind"
        st.rerun()

st.title("✨ जुगनू AI")
st.caption("अरविंद सिंह | पर्सनल स्मार्ट साथी")

if st.session_state.voice_call:
    st.info("📞 Voice Call Mode चालू है — बोलें, जुगनू जवाब देगा और आवाज में सुनाएगा।")

for i, m in enumerate(st.session_state.messages):
    render_message(i, m)

if "pending_audio" in st.session_state:
    st.audio(st.session_state.pending_audio, format="audio/mp3", autoplay=True)
    del st.session_state.pending_audio

st.divider()
st.markdown("### 🧰 नीचे से बोलें, file लगाएँ या quick action चुनें")

tool1, tool2, tool3 = st.columns([1, 1, 1])

with tool1:
    audio_value = st.audio_input("🎙️ बोलें", key="voice_input")

with tool2:
    uploaded_file = st.file_uploader(
        "📎 PDF / TXT",
        type=["pdf", "txt"],
        key="document_upload"
    )

with tool3:
    uploaded_img = st.file_uploader(
        "🖼️ Image",
        type=["png", "jpg", "jpeg", "webp"],
        key="image_upload"
    )

if uploaded_file is not None:
    text, name = extract_document(uploaded_file)
    st.session_state.file_text = text
    st.session_state.file_name = name
    st.success(f"📄 {name} loaded — {len(text):,} characters")
    if text:
        with st.expander("📖 Document Preview"):
            st.text(text[:8000])

if uploaded_img is not None:
    try:
        img = Image.open(uploaded_img)
        st.session_state.uploaded_image = img
        st.image(img, caption="Uploaded Image", width=500)
    except Exception as e:
        st.error(f"Image error: {e}")

st.markdown("### ⚡ Quick Actions")
quick_buttons()

voice_prompt = ""
if audio_value is not None:
    try:
        raw = audio_value.getvalue()
        audio_hash = hashlib.sha256(raw).hexdigest()
        if audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = audio_hash
            voice_prompt, err = transcribe_audio(io.BytesIO(raw))
            if err:
                st.error(err)
            elif voice_prompt:
                st.info(f"🎙️ आपने कहा: {voice_prompt}")
    except Exception as e:
        st.error(f"Voice error: {e}")

prompt = st.chat_input("जुगनू से कुछ भी पूछें...")

final_prompt = prompt or voice_prompt or st.session_state.quick_prompt
if final_prompt:
    st.session_state.quick_prompt = ""
    process_prompt(final_prompt, st.session_state.file_text)
    st.rerun()

st.markdown("---")
st.caption(
    "जुगनू AI • Groq GPT-OSS • Whisper Voice • SQLite Memory • PDF Reader • Web Search"
)
