import os
import re
import io
import json
import time
import hashlib
import sqlite3
from datetime import datetime
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import streamlit as st
from groq import Groq
from gtts import gTTS
from pypdf import PdfReader
from PIL import Image

try:
    from duckduckgo_search import DDGS
except Exception:
    try:
        from ddgs import DDGS
    except Exception:
        DDGS = None

st.set_page_config(
    page_title="जुगनू AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_NAME = "jugnu_data.db"
DEFAULT_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"
WHISPER_MODEL = "whisper-large-v3-turbo"
MAX_PDF_CHARS = 50000
MAX_SEARCH_RESULTS = 5

def clean_text(text):
    if text is None:
        return ""
    return (
        str(text)
        .replace("\u00a0", " ")
        .replace("\u2007", " ")
        .replace("\u202f", " ")
        .replace("\ufeff", "")
    )

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY,
            name TEXT,
            plan TEXT DEFAULT 'FREE',
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            username TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            task TEXT,
            remind_at TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            memory TEXT,
            created_at TEXT
        )
    """)
    cur.execute(
        "INSERT OR IGNORE INTO users(username,name,plan,created_at) VALUES(?,?,?,?)",
        ("arvind", "अरविंद सिंह", "VIP PRO", datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()

init_db()

def current_user():
    if "username" not in st.session_state:
        st.session_state.username = st.query_params.get("user", "arvind")
    return st.session_state.username

def get_user(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return row

def save_message(conversation_id, username, role, content):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages(conversation_id,username,role,content,created_at) VALUES(?,?,?,?,?)",
        (conversation_id, username, role, clean_text(content), datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()

def create_conversation(username, title="नई चैट"):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations(username,title,created_at) VALUES(?,?,?)",
        (username, clean_text(title)[:80] or "नई चैट", datetime.now().isoformat(timespec="seconds")),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid

def get_conversations(username, search=""):
    conn = get_db()
    if search.strip():
        rows = conn.execute(
            "SELECT * FROM conversations WHERE username=? AND title LIKE ? ORDER BY id DESC",
            (username, f"%{search.strip()}%"),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE username=? ORDER BY id DESC",
            (username,),
        ).fetchall()
    conn.close()
    return rows

def get_messages(conversation_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY id ASC",
        (conversation_id,),
    ).fetchall()
    conn.close()
    return rows

def get_memories(username):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM user_memories WHERE username=? ORDER BY id DESC",
        (username,),
    ).fetchall()
    conn.close()
    return rows

def add_memory(username, memory):
    memory = clean_text(memory).strip()
    if not memory:
        return
    conn = get_db()
    conn.execute(
        "INSERT INTO user_memories(username,memory,created_at) VALUES(?,?,?)",
        (username, memory, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()

def delete_memory(memory_id, username):
    conn = get_db()
    conn.execute("DELETE FROM user_memories WHERE id=? AND username=?", (memory_id, username))
    conn.commit()
    conn.close()

def save_note(username, task, remind_at):
    conn = get_db()
    conn.execute(
        "INSERT INTO notes(username,task,remind_at,created_at) VALUES(?,?,?,?)",
        (username, clean_text(task), clean_text(remind_at), datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()

def get_notes(username):
    conn = get_db()
    rows = conn.execute("SELECT * FROM notes WHERE username=? ORDER BY id DESC", (username,)).fetchall()
    conn.close()
    return rows

def delete_note(note_id, username):
    conn = get_db()
    conn.execute("DELETE FROM notes WHERE id=? AND username=?", (note_id, username))
    conn.commit()
    conn.close()

def get_or_create_conversation(username):
    if st.session_state.get("conversation_id"):
        return st.session_state.conversation_id
    cid = create_conversation(username)
    st.session_state.conversation_id = cid
    return cid

def new_chat():
    st.session_state.conversation_id = create_conversation(current_user())
    st.session_state.quick_prompt = ""
    st.session_state.pdf_text = ""
    st.session_state.pdf_name = ""
    st.session_state.image_name = ""
    st.session_state.voice_text = ""
    st.session_state.last_audio_hash = ""
    st.session_state.messages_cache = []
    st.rerun()

def get_api_key():
    return st.session_state.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")

def get_client():
    key = get_api_key()
    if not key:
        return None
    return Groq(api_key=key)

def extract_pdf(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return clean_text("\n\n".join(parts))
    except Exception as e:
        return f"PDF पढ़ने में समस्या: {e}"

def extract_text_file(uploaded_file):
    try:
        return clean_text(uploaded_file.read().decode("utf-8", errors="ignore"))
    except Exception as e:
        return f"TXT पढ़ने में समस्या: {e}"

def split_document(text, size=3500):
    text = clean_text(text)
    if not text:
        return []
    return [text[i:i + size] for i in range(0, len(text), size)]

def document_context(query, text, max_chunks=8):
    if not text:
        return ""
    chunks = split_document(text)
    if not chunks:
        return ""
    words = {
        w.lower()
        for w in re.findall(r"[A-Za-zА-Яа-яÀ-ÿ\u0900-\u097F0-9]{3,}", clean_text(query))
    }
    scored = []
    for i, chunk in enumerate(chunks):
        low = chunk.lower()
        score = sum(low.count(w) for w in words)
        scored.append((score, i, chunk))
    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    selected = [x[2] for x in scored[:max_chunks]]
    result = "\n\n--- PDF/FILE SECTION ---\n".join(selected)
    return result[:MAX_PDF_CHARS]

def should_search_web(query, explicit=False):
    if explicit:
        return True
    q = query.lower()
    triggers = [
        "आज", "अभी", "लेटेस्ट", "latest", "today", "current", "now",
        "मौसम", "weather", "news", "समाचार", "भाव", "price", "कीमत",
        "result", "परिणाम", "सरकारी योजना", "scheme", "2026"
    ]
    return any(x in q for x in triggers)

def live_search(query):
    if DDGS is None:
        return []
    try:
        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=MAX_SEARCH_RESULTS):
                results.append({
                    "title": clean_text(item.get("title", "")),
                    "url": item.get("href", ""),
                    "snippet": clean_text(item.get("body", "")),
                })
        return results
    except Exception:
        return []

def weather_description(code):
    codes = {
        0: "साफ आसमान", 1: "मुख्यतः साफ", 2: "आंशिक बादल", 3: "बादल",
        45: "कोहरा", 48: "कोहरा", 51: "हल्की बूंदाबांदी", 53: "बूंदाबांदी",
        55: "घनी बूंदाबांदी", 61: "हल्की बारिश", 63: "बारिश", 65: "तेज बारिश",
        71: "हल्की बर्फबारी", 73: "बर्फबारी", 75: "तेज बर्फबारी",
        80: "हल्की बारिश की बौछार", 81: "बारिश की बौछार", 82: "तेज बारिश की बौछार",
        95: "गरज के साथ बारिश", 96: "गरज और ओलावृष्टि", 99: "गरज और तेज ओलावृष्टि"
    }
    return codes.get(code, "मौसम की स्थिति उपलब्ध")

def get_weather(city):
    city = clean_text(city).strip()
    if not city:
        return None
    try:
        q = urlencode({"name": city, "count": 1, "language": "hi", "format": "json"})
        req = Request("https://geocoding-api.open-meteo.com/v1/search?" + q, headers={"User-Agent": "JugnuAI/2.0"})
        with urlopen(req, timeout=10) as r:
            geo = json.loads(r.read().decode("utf-8"))
        places = geo.get("results") or []
        if not places:
            return None
        place = places[0]
        lat, lon = place["latitude"], place["longitude"]
        q2 = urlencode({
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto"
        })
        req2 = Request("https://api.open-meteo.com/v1/forecast?" + q2, headers={"User-Agent": "JugnuAI/2.0"})
        with urlopen(req2, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        cur = data.get("current", {})
        temp = cur.get("temperature_2m")
        feels = cur.get("apparent_temperature")
        humidity = cur.get("relative_humidity_2m")
        wind = cur.get("wind_speed_10m")
        code = cur.get("weather_code")
        place_name = place.get("name", city)
        country = place.get("country", "")
        snippet = (
            f"{place_name}, {country}: अभी तापमान {temp}°C, महसूस {feels}°C, "
            f"{weather_description(code)}, नमी {humidity}%, हवा {wind} km/h।"
        )
        return {
            "title": f"Current weather — {place_name}",
            "url": "https://open-meteo.com/",
            "snippet": snippet,
        }
    except Exception:
        return None

def search_context(results):
    if not results:
        return ""
    blocks = []
    for i, item in enumerate(results, 1):
        blocks.append(
            f"[SOURCE {i}]\n"
            f"Title: {item['title']}\n"
            f"URL: {item['url']}\n"
            f"Snippet: {item['snippet']}"
        )
    return "\n\n".join(blocks)

def detect_memory_request(text):
    text = clean_text(text).strip()
    patterns = [
        r"याद रखना[:\s]*(.+)",
        r"इसे याद रखना[:\s]*(.+)",
        r"मुझे याद रखना[:\s]*(.+)",
        r"remember that[:\s]*(.+)",
        r"remember this[:\s]*(.+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return m.group(1).strip()
    return ""

def generate_image_url(prompt):
    prompt = clean_text(prompt).strip()
    if not prompt:
        prompt = "beautiful cinematic Indian landscape"
    safe = quote(prompt)
    return f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&nologo=true"

def is_image_request(text):
    q = text.lower()
    triggers = [
        "image", "photo", "picture", "generate an image", "create image",
        "फोटो", "तस्वीर", "चित्र", "इमेज", "बना दो", "बनाओ"
    ]
    return any(x in q for x in triggers)

def image_prompt_from_text(text):
    q = clean_text(text)
    replacements = [
        "generate an image of", "create an image of", "make an image of",
        "generate image", "create image", "फोटो बनाओ", "तस्वीर बनाओ",
        "इमेज बनाओ", "चित्र बनाओ"
    ]
    low = q.lower()
    for r in replacements:
        idx = low.find(r.lower())
        if idx >= 0:
            return q[idx + len(r):].strip(" :-")
    return q

def transcribe_audio(audio_file):
    client = get_client()
    if client is None:
        return "", "GROQ_API_KEY नहीं मिला।"
    try:
        audio_bytes = audio_file.getvalue()
        result = client.audio.transcriptions.create(
            file=("voice.wav", audio_bytes),
            model=WHISPER_MODEL,
            response_format="text",
        )
        return clean_text(result), ""
    except Exception as e:
        return "", f"Voice transcription error: {e}"

def tts_audio(text, language="hi", slow=False):
    text = clean_text(text).strip()
    if not text:
        return None
    try:
        lang = "hi" if language in ["हिंदी", "Hindi", "हिन्दी"] else "en"
        key = hashlib.sha256(f"{lang}|{slow}|{text}".encode("utf-8")).hexdigest()
        cache_dir = ".jugnu_tts"
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{key}.mp3")
        if not os.path.exists(path):
            gTTS(text=text[:4500], lang=lang, slow=slow).save(path)
        return path
    except Exception:
        return None

def system_prompt(language, bot_mode, memories, document_name=""):
    memory_text = "\n".join(f"- {m['memory']}" for m in memories[:20]) or "- कोई saved memory नहीं"
    mode_map = {
        "मारवाड़ी / राजस्थानी": "जरूरत होने पर सरल, मीठी और स्वाभाविक मारवाड़ी/राजस्थानी में जवाब दो।",
        "दोस्ताना": "दोस्त की तरह सरल, गर्मजोशी से जवाब दो।",
        "शिक्षक": "शिक्षक की तरह step-by-step और आसान भाषा में समझाओ।",
        "कहानीकार": "कहानीकार की तरह रोचक भाषा का उपयोग करो।",
    }
    language_instruction = (
        "मुख्य जवाब हिंदी में दो।"
        if language in ["हिंदी", "Hindi", "हिन्दी"]
        else "Answer mainly in English."
    )
    return f"""
तुम Jugnu AI हो, अरविंद सिंह के personal smart companion हो।
{language_instruction}
{mode_map.get(bot_mode, mode_map["दोस्ताना"])}

नियम:
- तथ्य न पता हो तो साफ कहो कि जानकारी उपलब्ध नहीं है।
- Web search context दिया गया हो तो current facts के लिए उसी का उपयोग करो।
- Search sources को देखकर URL गढ़ना नहीं।
- PDF/file context दिया गया हो तो उसी से उत्तर दो और context से बाहर की बात को स्पष्ट रूप से अलग बताओ।
- जवाब साफ, उपयोगी और जरूरत के अनुसार छोटा रखो।
- अरविंद सिंह के बारे में creator पूछे जाने पर बताओ कि वे Jugnu AI के creator हैं और Gaon Doojasar, Shri Mohangarh से हैं।
- किसी व्यक्ति के बारे में निजी/असत्य जानकारी मत गढ़ो।

Saved memory:
{memory_text}

Current uploaded document:
{document_name or "कोई document नहीं"}
"""

def call_llm(user_text, language, bot_mode, memories, web_results=None, doc_context=""):
    client = get_client()
    if client is None:
        return "GROQ_API_KEY सेट नहीं है। Sidebar में अपना Groq API key डालें।", DEFAULT_MODEL

    messages = [
        {"role": "system", "content": system_prompt(language, bot_mode, memories, st.session_state.get("pdf_name", ""))}
    ]
    if web_results:
        messages.append({
            "role": "system",
            "content": "Live web search context:\n" + search_context(web_results)
        })
    if doc_context:
        messages.append({
            "role": "system",
            "content": "Uploaded PDF/TXT context:\n" + doc_context
        })
    for item in st.session_state.get("messages_cache", [])[-12:]:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": clean_text(user_text)})

    for model in [DEFAULT_MODEL, FALLBACK_MODEL]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.5,
                max_tokens=1200,
            )
            answer = clean_text(response.choices[0].message.content)
            if answer:
                return answer, model
        except Exception as e:
            last_error = str(e)
    return f"AI response error: {last_error}", FALLBACK_MODEL

def add_chat_to_state(role, content):
    if "messages_cache" not in st.session_state:
        st.session_state.messages_cache = []
    st.session_state.messages_cache.append({"role": role, "content": clean_text(content)})

def render_message(role, content, idx, username):
    if role == "user":
        with st.chat_message("user"):
            st.markdown(content)
    else:
        with st.chat_message("assistant"):
            st.markdown(content)
            image_match = re.search(r"https://image\.pollinations\.ai/prompt/[^\s]+", content)
            if image_match:
                image_url = image_match.group(0)
                try:
                    st.image(image_url, caption="🎨 Jugnu AI Image", use_container_width=True)
                except Exception:
                    st.info("Image link ऊपर दिया गया है।")
            if content and not content.startswith("AI response error"):
                if st.button("🔊 सुनें", key=f"listen_{username}_{idx}"):
                    lang = st.session_state.get("language", "हिंदी")
                    slow = st.session_state.get("voice_speed", "सामान्य") == "धीमी"
                    path = tts_audio(content, lang, slow)
                    if path:
                        st.audio(path, format="audio/mp3")
                    else:
                        st.warning("Voice response अभी generate नहीं हो पाया।")

username = current_user()
user = get_user(username)
if not user:
    username = "arvind"
    st.session_state.username = username
    st.query_params["user"] = username
    user = get_user(username)

if "language" not in st.session_state:
    st.session_state.language = "हिंदी"
if "bot_mode" not in st.session_state:
    st.session_state.bot_mode = "दोस्ताना"
if "voice_speed" not in st.session_state:
    st.session_state.voice_speed = "सामान्य"
if "web_search" not in st.session_state:
    st.session_state.web_search = False
if "voice_call" not in st.session_state:
    st.session_state.voice_call = False
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""
if "pdf_name" not in st.session_state:
    st.session_state.pdf_name = ""
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = create_conversation(username, "नई चैट")
if "messages_cache" not in st.session_state:
    st.session_state.messages_cache = [
        {"role": r["role"], "content": r["content"]}
        for r in get_messages(st.session_state.conversation_id)
    ]
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = ""
if "quick_prompt" not in st.session_state:
    st.session_state.quick_prompt = ""
if "weather_city" not in st.session_state:
    st.session_state.weather_city = "Jaipur"
if "last_sources" not in st.session_state:
    st.session_state.last_sources = []

with st.sidebar:
    st.markdown("## ✨ जुगनू AI")
    st.markdown(f"**👤 {user['name']}**  \n**👑 {user['plan']}**")

    if st.button("➕ नई चैट", use_container_width=True):
        new_chat()

    if st.button("🚪 लॉगआउट", use_container_width=True):
        st.session_state.pop("username", None)
        st.query_params.clear()
        st.info("Session logout हो गया। Demo app में default user फिर से उपलब्ध रहेगा।")

    st.divider()
    st.subheader("🎙️ Voice AI")
    st.session_state.voice_call = st.toggle(
        "Voice Call Mode",
        value=st.session_state.voice_call,
        help="Voice input के बाद AI answer को automatically सुनाने की कोशिश करेगा।",
    )

    st.subheader("📍 Weather City")
    st.session_state.weather_city = st.text_input("मौसम किस शहर का?", value=st.session_state.get("weather_city", "Jaipur"))

    st.subheader("⚙️ Settings")
    st.session_state.language = st.selectbox(
        "भाषा", ["हिंदी", "English"], index=0 if st.session_state.language == "हिंदी" else 1
    )
    st.session_state.bot_mode = st.selectbox(
        "Bot Mode",
        ["दोस्ताना", "मारवाड़ी / राजस्थानी", "शिक्षक", "कहानीकार"],
        index=["दोस्ताना", "मारवाड़ी / राजस्थानी", "शिक्षक", "कहानीकार"].index(st.session_state.bot_mode),
    )
    st.session_state.voice_speed = st.selectbox(
        "Voice Speed", ["सामान्य", "धीमी"],
        index=0 if st.session_state.voice_speed == "सामान्य" else 1,
    )

    st.divider()
    st.subheader("🔐 Groq API")
    key_input = st.text_input(
        "GROQ_API_KEY",
        type="password",
        value=st.session_state.get("groq_api_key", ""),
        placeholder="gsk_...",
    )
    if key_input:
        st.session_state.groq_api_key = key_input
    elif os.getenv("GROQ_API_KEY"):
        st.caption("Environment variable से API key मिली है।")

    st.divider()
    st.subheader("🧠 Memory Bank")
    memory_text = st.text_input("क्या याद रखना है?", key="memory_input")
    if st.button("💾 Memory Save", use_container_width=True):
        if memory_text.strip():
            add_memory(username, memory_text)
            st.success("Memory save हो गई।")
            st.rerun()

    memories = get_memories(username)
    for m in memories[:10]:
        c1, c2 = st.columns([5, 1])
        c1.caption("🧠 " + m["memory"])
        if c2.button("×", key=f"delmem_{m['id']}"):
            delete_memory(m["id"], username)
            st.rerun()

    st.divider()
    st.subheader("⏰ Smart Reminder")
    task = st.text_input("Task / Diary", key="note_task")
    remind_at = st.text_input("समय", placeholder="कल सुबह 8 बजे")
    if st.button("➕ Reminder Save", use_container_width=True):
        if task.strip():
            save_note(username, task, remind_at)
            st.success("Reminder save हो गया।")
            st.rerun()
    for n in get_notes(username)[:8]:
        c1, c2 = st.columns([5, 1])
        c1.caption(f"⏰ {n['task']} — {n['remind_at']}")
        if c2.button("×", key=f"delnote_{n['id']}"):
            delete_note(n["id"], username)
            st.rerun()

    st.divider()
    st.subheader("🔎 Chat Search")
    search = st.text_input("पुरानी chat खोजें")
    for c in get_conversations(username, search)[:15]:
        if st.button(f"💬 {c['title'][:35]}", key=f"conv_{c['id']}", use_container_width=True):
            st.session_state.conversation_id = c["id"]
            st.session_state.messages_cache = [
                {"role": r["role"], "content": r["content"]}
                for r in get_messages(c["id"])
            ]
            st.rerun()

    st.divider()
    st.subheader("👑 VIP PRO")
    st.write("Current plan:", user["plan"])
    st.caption("Payment gateway जोड़ने के बाद VIP entitlement को payment status से connect किया जा सकता है.")

st.title("✨ जुगनू AI")
st.caption("अरविंद सिंह | पर्सनल स्मार्ट साथी")

top1, top2, top3, top4 = st.columns(4)
with top1:
    if st.button("👑 निर्माता", use_container_width=True):
        st.session_state.quick_prompt = "Jugnu AI का creator कौन है?"
with top2:
    if st.button("⏰ समय", use_container_width=True):
        st.session_state.quick_prompt = "अभी का समय बताओ।"
with top3:
    if st.button("🌤 मौसम", use_container_width=True):
        st.session_state.quick_prompt = "आज का मौसम कैसा है? Web search करके बताओ।"
with top4:
    if st.button("😄 चुटकुला", use_container_width=True):
        st.session_state.quick_prompt = "एक मजेदार हिंदी चुटकुला सुनाओ।"

b1, b2, b3, b4 = st.columns(4)
with b1:
    if st.button("🎨 फोटो", use_container_width=True):
        st.session_state.quick_prompt = "एक सुंदर राजस्थान के रेगिस्तान की cinematic photo बनाओ।"
with b2:
    if st.button("🎯 क्विज़", use_container_width=True):
        st.session_state.quick_prompt = "REET/RAS level का एक GK quiz question पूछो।"
with b3:
    if st.button("🍎 सेहत", use_container_width=True):
        st.session_state.quick_prompt = "स्वस्थ रहने के लिए 5 सामान्य daily habits बताओ।"
with b4:
    if st.button("💬 मारवाड़ी", use_container_width=True):
        st.session_state.quick_prompt = "मारवाड़ी में प्यार से एक छोटी सी बात बोलो।"

if st.session_state.pdf_text:
    st.info(f"📄 Loaded: {st.session_state.pdf_name} — अब आप इससे सवाल पूछ सकते हैं।")
    if st.button("🗑️ PDF हटाएँ"):
        st.session_state.pdf_text = ""
        st.session_state.pdf_name = ""
        st.rerun()

for i, msg in enumerate(st.session_state.messages_cache):
    render_message(msg["role"], msg["content"], i, username)

st.divider()
st.subheader("🧰 Tools")

tool1, tool2, tool3 = st.columns([1, 1, 1])
with tool1:
    audio_value = st.audio_input("🎙️ बोलें")
with tool2:
    uploaded_file = st.file_uploader("📎 PDF / TXT", type=["pdf", "txt"])
with tool3:
    uploaded_image = st.file_uploader("🖼️ Image Preview", type=["png", "jpg", "jpeg", "webp"])

if uploaded_file is not None:
    file_hash = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
    if st.session_state.get("file_hash") != file_hash:
        st.session_state.file_hash = file_hash
        if uploaded_file.name.lower().endswith(".pdf"):
            st.session_state.pdf_text = extract_pdf(uploaded_file)
        else:
            st.session_state.pdf_text = extract_text_file(uploaded_file)
        st.session_state.pdf_name = uploaded_file.name
        st.rerun()

if uploaded_image is not None:
    try:
        img = Image.open(uploaded_image)
        st.image(img, caption=uploaded_image.name, width=320)
    except Exception as e:
        st.error(f"Image preview error: {e}")

c1, c2, c3 = st.columns(3)
with c1:
    st.session_state.web_search = st.toggle(
        "🌐 Web Search",
        value=st.session_state.web_search,
        help="Current/latest information के लिए web search करें।",
    )
with c2:
    pdf_mode = st.toggle(
        "📄 PDF से जवाब",
        value=bool(st.session_state.pdf_text),
        disabled=not bool(st.session_state.pdf_text),
    )
with c3:
    st.caption("🎙️ Voice → Whisper → AI → 🔊 Voice")

prompt_from_voice = ""
if audio_value is not None:
    audio_hash = hashlib.sha256(audio_value.getvalue()).hexdigest()
    if audio_hash != st.session_state.last_audio_hash:
        st.session_state.last_audio_hash = audio_hash
        with st.spinner("🎙️ आपकी आवाज़ समझ रहा हूँ..."):
            prompt_from_voice, voice_error = transcribe_audio(audio_value)
        if voice_error:
            st.warning(voice_error)
        elif prompt_from_voice:
            st.info(f"आपने कहा: **{prompt_from_voice}**")

chat_prompt = st.chat_input("जुगनू से कुछ भी पूछें...")

prompt = (
    prompt_from_voice.strip()
    if prompt_from_voice.strip()
    else (st.session_state.quick_prompt.strip() if st.session_state.quick_prompt.strip() else chat_prompt)
)

if prompt:
    st.session_state.quick_prompt = ""
    cid = get_or_create_conversation(username)

    if not st.session_state.messages_cache:
        conn = get_db()
        conn.execute(
            "UPDATE conversations SET title=? WHERE id=?",
            (clean_text(prompt)[:80], cid),
        )
        conn.commit()
        conn.close()

    add_chat_to_state("user", prompt)
    save_message(cid, username, "user", prompt)

    explicit_web = st.session_state.web_search
    use_web = should_search_web(prompt, explicit_web)
    web_results = live_search(prompt) if use_web else []
    if "मौसम" in prompt.lower() or "weather" in prompt.lower():
        weather_result = get_weather(st.session_state.get("weather_city", "Jaipur"))
        if weather_result:
            web_results = [weather_result] + web_results

    doc_ctx = ""
    if pdf_mode and st.session_state.pdf_text:
        doc_ctx = document_context(prompt, st.session_state.pdf_text)

    requested_memory = detect_memory_request(prompt)
    if requested_memory:
        add_memory(username, requested_memory)

    if is_image_request(prompt):
        img_prompt = image_prompt_from_text(prompt)
        image_url = generate_image_url(img_prompt)
        answer = f"🎨 आपकी image तैयार है:\n\n{image_url}"
        model_used = "image-generator"
    else:
        with st.spinner("✨ जुगनू सोच रहा है..."):
            answer, model_used = call_llm(
                prompt,
                st.session_state.language,
                st.session_state.bot_mode,
                get_memories(username),
                web_results=web_results,
                doc_context=doc_ctx,
            )

    add_chat_to_state("assistant", answer)
    save_message(cid, username, "assistant", answer)

    if web_results:
        st.session_state.last_sources = web_results

    st.rerun()

if st.session_state.get("last_sources"):
    with st.expander("🌐 Web Sources"):
        for i, source in enumerate(st.session_state.last_sources, 1):
            st.markdown(f"**{i}. {source['title']}**")
            if source["url"]:
                st.markdown(source["url"])
            if source["snippet"]:
                st.caption(source["snippet"])

st.divider()
st.caption(
    "Jugnu AI v2 • Groq AI + Whisper + gTTS + Web Search + Memory + PDF Reader + Image Generation"
)
