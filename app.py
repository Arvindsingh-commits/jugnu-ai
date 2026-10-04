import os
import io
import re
import base64
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
    DDGS_AVAILABLE = True
except Exception:
    DDGS_AVAILABLE = False

try:
    from google import genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False


# =========================================================
# JUGNU AI - BASIC CONFIG
# =========================================================

APP_NAME = "जुगनू AI"

DB_FILE = "jugnu_data.db"

CHAT_MODEL = "openai/gpt-oss-120b"
FALLBACK_CHAT_MODEL = "openai/gpt-oss-20b"

WHISPER_MODEL = "whisper-large-v3-turbo"

# Current Gemini image model
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="जुगनू AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
<style>

.stApp {
    background: #ffffff;
}

.block-container {
    max-width: 1200px;
    padding-top: 1rem;
    padding-bottom: 5rem;
}

[data-testid="stSidebar"] {
    background: #f7f7f8;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.2rem;
}

.jugnu-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 0;
}

.jugnu-subtitle {
    color: #777;
    font-size: 14px;
    margin-top: 2px;
}

.jugnu-card {
    border: 1px solid #e5e5e5;
    border-radius: 16px;
    padding: 18px;
    background: white;
    margin-bottom: 14px;
}

.jugnu-small {
    color: #777;
    font-size: 13px;
}

.jugnu-user {
    background: #f3f4f6;
    border-radius: 16px;
    padding: 12px 16px;
    margin: 8px 0;
}

.jugnu-ai {
    background: #ffffff;
    border-radius: 16px;
    padding: 12px 16px;
    margin: 8px 0;
    border: 1px solid #eeeeee;
}

.creator-box {
    background: #f7f7f8;
    border-radius: 15px;
    padding: 15px;
    margin-top: 15px;
}

.vip-box {
    border: 1px solid #ddd;
    border-radius: 15px;
    padding: 15px;
    background: #fafafa;
}

</style>
""",
    unsafe_allow_html=True
)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT,
            password TEXT,
            plan TEXT DEFAULT 'FREE',
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT,
            password TEXT,
            plan TEXT DEFAULT 'FREE',
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            username TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            content TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            memory TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            username TEXT PRIMARY KEY,
            language TEXT DEFAULT 'Hindi',
            bot_mode TEXT DEFAULT 'Smart',
            voice_speed INTEGER DEFAULT 1
        )
        """
    )

    conn.commit()

    # Default Arvind account
    existing = cur.execute(
        "SELECT * FROM users WHERE username=?",
        ("arvind",)
    ).fetchone()

    if not existing:

        password_hash = hash_password("Jugnu@123")

        cur.execute(
            """
            INSERT INTO users
            (username, name, password, plan, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "arvind",
                "अरविंद सिंह",
                password_hash,
                "VIP PRO",
                now()
            )
        )

    conn.commit()
    conn.close()


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def safe_get_secret(name):

    try:
        value = st.secrets.get(name)

        if value:
            return value
    except Exception:
        pass

    return os.getenv(name)


def get_groq_client():

    key = safe_get_secret("GROQ_API_KEY")

    if not key:
        return None

    try:
        return Groq(api_key=key)
    except Exception:
        return None


def get_gemini_client():

    key = safe_get_secret("GEMINI_API_KEY")

    if not key:
        return None

    if not GEMINI_AVAILABLE:
        return None

    try:
        return genai.Client(api_key=key)
    except Exception:
        return None


def escape_text(text):

    if text is None:
        return ""

    return str(text)


# =========================================================
# USER AUTH
# =========================================================

def login_user(username, password):

    conn = get_db()

    user = conn.execute(
        """
        SELECT * FROM users
        WHERE username=? AND password=?
        """,
        (
            username.strip().lower(),
            hash_password(password)
        )
    ).fetchone()

    conn.close()

    return user


def create_user(username, name, password):

    username = username.strip().lower()
    name = name.strip()

    if not username or not name or not password:
        return False, "सभी fields भरें।"

    if len(password) < 6:
        return False, "Password कम से कम 6 characters का होना चाहिए।"

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT INTO users
            (username, name, password, plan, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                name,
                hash_password(password),
                "FREE",
                now()
            )
        )

        conn.commit()
        conn.close()

        return True, "Account बन गया।"

    except sqlite3.IntegrityError:

        conn.close()

        return False, "यह username पहले से मौजूद है।"


def change_password(username, old_password, new_password):

    conn = get_db()

    user = conn.execute(
        """
        SELECT * FROM users
        WHERE username=? AND password=?
        """,
        (
            username,
            hash_password(old_password)
        )
    ).fetchone()

    if not user:
        conn.close()
        return False, "पुराना password गलत है।"

    if len(new_password) < 6:
        conn.close()
        return False, "नया password कम से कम 6 characters का रखें।"

    conn.execute(
        """
        UPDATE users
        SET password=?
        WHERE username=?
        """,
        (
            hash_password(new_password),
            username
        )
    )

    conn.commit()
    conn.close()

    return True, "Password successfully बदल गया।"


# =========================================================
# CONVERSATIONS
# =========================================================

def create_conversation(username, title="नई बातचीत"):

    conn = get_db()

    cur = conn.execute(
        """
        INSERT INTO conversations
        (username, title, created_at)
        VALUES (?, ?, ?)
        """,
        (
            username,
            title,
            now()
        )
    )

    conversation_id = cur.lastrowid

    conn.commit()
    conn.close()

    return conversation_id


def get_conversations(username):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT * FROM conversations
        WHERE username=?
        ORDER BY id DESC
        """,
        (username,)
    ).fetchall()

    conn.close()

    return rows


def get_messages(conversation_id):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT * FROM messages
        WHERE conversation_id=?
        ORDER BY id ASC
        """,
        (conversation_id,)
    ).fetchall()

    conn.close()

    return rows


def save_message(
    conversation_id,
    username,
    role,
    content
):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO messages
        (conversation_id, username, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            username,
            role,
            content,
            now()
        )
    )

    conn.commit()
    conn.close()


def update_conversation_title(
    conversation_id,
    title
):

    conn = get_db()

    conn.execute(
        """
        UPDATE conversations
        SET title=?
        WHERE id=?
        """,
        (
            title[:80],
            conversation_id
        )
    )

    conn.commit()
    conn.close()


def delete_conversation(conversation_id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM messages
        WHERE conversation_id=?
        """,
        (conversation_id,)
    )

    conn.execute(
        """
        DELETE FROM conversations
        WHERE id=?
        """,
        (conversation_id,)
    )

    conn.commit()
    conn.close()


# =========================================================
# MEMORY
# =========================================================

def add_memory(username, memory):

    if not memory.strip():
        return

    conn = get_db()

    conn.execute(
        """
        INSERT INTO user_memories
        (username, memory, created_at)
        VALUES (?, ?, ?)
        """,
        (
            username,
            memory.strip(),
            now()
        )
    )

    conn.commit()
    conn.close()


def get_memories(username):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT * FROM user_memories
        WHERE username=?
        ORDER BY id DESC
        LIMIT 20
        """,
        (username,)
    ).fetchall()

    conn.close()

    return rows


# =========================================================
# SETTINGS
# =========================================================

def get_settings(username):

    conn = get_db()

    row = conn.execute(
        """
        SELECT * FROM app_settings
        WHERE username=?
        """,
        (username,)
    ).fetchone()

    if not row:

        conn.execute(
            """
            INSERT INTO app_settings
            (username, language, bot_mode, voice_speed)
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                "Hindi",
                "Smart",
                1
            )
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT * FROM app_settings
            WHERE username=?
            """,
            (username,)
        ).fetchone()

    conn.close()

    return row


def save_settings(
    username,
    language,
    bot_mode,
    voice_speed
):

    conn = get_db()

    conn.execute(
        """
        INSERT OR REPLACE INTO app_settings
        (username, language, bot_mode, voice_speed)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            language,
            bot_mode,
            voice_speed
        )
    )

    conn.commit()
    conn.close()


# =========================================================
# PDF / TEXT
# =========================================================

def extract_pdf_text(uploaded_file):

    try:

        reader = PdfReader(uploaded_file)

        text = ""

        for page in reader.pages:

            try:
                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"
            except Exception:
                continue

        return text.strip()

    except Exception as e:

        return f"PDF पढ़ने में समस्या: {e}"


def extract_text_file(uploaded_file):

    try:

        raw = uploaded_file.read()

        return raw.decode(
            "utf-8",
            errors="ignore"
        )

    except Exception as e:

        return f"Text file पढ़ने में समस्या: {e}"


# =========================================================
# WEB SEARCH
# =========================================================

def web_search(query, max_results=5):

    if not DDGS_AVAILABLE:
        return "Web search package उपलब्ध नहीं है।"

    try:

        results = []

        with DDGS() as ddgs:

            for item in ddgs.text(
                query,
                max_results=max_results
            ):

                title = item.get("title", "")
                body = item.get("body", "")
                href = item.get("href", "")

                results.append(
                    f"Title: {title}\n"
                    f"Summary: {body}\n"
                    f"URL: {href}"
                )

        if not results:
            return "कोई web result नहीं मिला।"

        return "\n\n".join(results)

    except Exception as e:

        return f"Web search में समस्या: {e}"


# =========================================================
# CREATOR INFORMATION
# =========================================================

def creator_answer(text):

    lower = text.lower()

    creator_words = [
        "निर्माता कौन",
        "किसने बनाया",
        "creator",
        "who made jugnu",
        "jugnu ai किसने",
        "जुगनू ai किसने"
    ]

    if any(word in lower for word in creator_words):

        return (
            "जुगनू AI के निर्माता **अरविंद सिंह** हैं।\n\n"
            "उनके पिता का नाम **Mr Rewant Singh** है।\n"
            "गाँव: **Doojasar**\n"
            "वर्तमान स्थान: **Shri Mohangarh**"
        )

    return None


# =========================================================
# IMAGE REQUEST DETECTION
# =========================================================

def is_image_request(text):

    text = text.lower().strip()

    keywords = [
        "image बनाओ",
        "image banao",
        "photo बनाओ",
        "photo banao",
        "picture बनाओ",
        "picture banao",
        "फोटो बनाओ",
        "तस्वीर बनाओ",
        "चित्र बनाओ",
        "generate image",
        "generate a image",
        "generate an image",
        "create image",
        "create a picture",
        "make image",
        "make a photo",
        "draw image",
        "draw a picture",
        "ai image"
    ]

    return any(
        key in text
        for key in keywords
    )


# =========================================================
# GEMINI IMAGE GENERATION
# =========================================================

def generate_image_with_gemini(prompt):

    client = get_gemini_client()

    if client is None:

        return None, (
            "Gemini API connect नहीं हुआ। "
            "Streamlit Secrets में GEMINI_API_KEY check करें।"
        )

    try:

        # IMPORTANT:
        # यहाँ response_format में image/png नहीं भेज रहे।
        # Google के current Gemini image-generation examples
        # में direct interactions.create() से image generate की जा सकती है.

        interaction = client.interactions.create(
            model=GEMINI_IMAGE_MODEL,
            input=prompt
        )

        # -------------------------------------------------
        # Method 1: output_image
        # -------------------------------------------------

        output_image = getattr(
            interaction,
            "output_image",
            None
        )

        if output_image is not None:

            data = getattr(
                output_image,
                "data",
                None
            )

            if data:

                image_bytes = base64.b64decode(data)

                image = Image.open(
                    io.BytesIO(image_bytes)
                )

                return image, None

        # -------------------------------------------------
        # Method 2: interaction steps
        # -------------------------------------------------

        steps = getattr(
            interaction,
            "steps",
            None
        )

        if steps:

            for step in steps:

                content = getattr(
                    step,
                    "content",
                    None
                )

                if not content:
                    continue

                for block in content:

                    block_type = getattr(
                        block,
                        "type",
                        None
                    )

                    if block_type == "image":

                        data = getattr(
                            block,
                            "data",
                            None
                        )

                        if data:

                            image_bytes = base64.b64decode(
                                data
                            )

                            image = Image.open(
                                io.BytesIO(image_bytes)
                            )

                            return image, None

        return None, (
            "Gemini ने image data वापस नहीं दिया। "
            "कृपया दोबारा कोशिश करें।"
        )

    except Exception as e:

        return None, str(e)


# =========================================================
# VOICE INPUT
# =========================================================

def transcribe_audio(audio_file):

    client = get_groq_client()

    if client is None:

        return None, (
            "GROQ_API_KEY नहीं मिली।"
        )

    try:

        audio_bytes = audio_file.read()

        result = client.audio.transcriptions.create(
            file=(
                audio_file.name,
                audio_bytes
            ),
            model=WHISPER_MODEL
        )

        return result.text, None

    except Exception as e:

        return None, str(e)


# =========================================================
# TEXT TO SPEECH
# =========================================================

def make_voice(text, language="hi"):

    try:

        mp3 = io.BytesIO()

        tts = gTTS(
            text=text,
            lang=language,
            slow=False
        )

        tts.write_to_fp(mp3)

        mp3.seek(0)

        return mp3.read()

    except Exception:

        return None


# =========================================================
# GROQ CHAT
# =========================================================

def ask_groq(
    user_message,
    history,
    username,
    language="Hindi",
    bot_mode="Smart",
    pdf_context="",
    web_context=""
):

    client = get_groq_client()

    if client is None:

        return (
            "GROQ_API_KEY नहीं मिली। "
            "Streamlit Secrets में GROQ_API_KEY check करें।"
        )

    memories = get_memories(username)

    memory_text = ""

    if memories:

        memory_text = "\n".join(
            [
                f"- {m['memory']}"
                for m in memories
            ]
        )

    system_prompt = f"""
You are Jugnu AI, a helpful Indian AI assistant.

User name: {username}

Language preference: {language}

Bot mode: {bot_mode}

Important creator information:
Jugnu AI creator is Arvind Singh.
His father is Mr Rewant Singh.
Village: Doojasar.
Current place: Shri Mohangarh.

User memories:
{memory_text}

PDF/Text context:
{pdf_context[:30000]}

Web search context:
{web_context[:15000]}

Instructions:
- Answer clearly and naturally.
- Prefer Hindi when the user speaks Hindi.
- If the user asks in Hinglish, answer in simple Hinglish/Hindi.
- Do not claim to have searched the web unless web context is actually supplied.
- Do not invent facts.
- Keep simple questions concise.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    for item in history[-12:]:

        messages.append(
            {
                "role": item["role"],
                "content": item["content"]
            }
        )

    messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )

    try:

        completion = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7
        )

        return completion.choices[0].message.content

    except Exception:

        try:

            completion = client.chat.completions.create(
                model=FALLBACK_CHAT_MODEL,
                messages=messages,
                temperature=0.7
            )

            return completion.choices[0].message.content

        except Exception as e:

            return f"AI response में समस्या आई: {e}"


# =========================================================
# INITIALIZE
# =========================================================

init_db()


# =========================================================
# SESSION STATE
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "name" not in st.session_state:
    st.session_state.name = ""

if "plan" not in st.session_state:
    st.session_state.plan = ""

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if "pdf_context" not in st.session_state:
    st.session_state.pdf_context = ""

if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = ""

if "last_generated_image" not in st.session_state:
    st.session_state.last_generated_image = None

if "last_generated_prompt" not in st.session_state:
    st.session_state.last_generated_prompt = ""


# =========================================================
# LOGIN PAGE
# =========================================================

if not st.session_state.logged_in:

    st.markdown(
        """
        <div style="text-align:center; padding:40px 0 20px;">
            <div class="jugnu-title">✨ जुगनू AI</div>
            <div class="jugnu-subtitle">
                आपका अपना AI Assistant
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs(
        [
            "🔐 Login",
            "📝 Create Account",
            "👤 Guest"
        ]
    )

    with tab1:

        username = st.text_input(
            "Username",
            key="login_username"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button(
            "Login",
            use_container_width=True
        ):

            user = login_user(
                username,
                password
            )

            if user:

                st.session_state.logged_in = True
                st.session_state.username = user["username"]
                st.session_state.name = user["name"]
                st.session_state.plan = user["plan"]

                st.session_state.conversation_id = (
                    create_conversation(
                        user["username"]
                    )
                )

                st.rerun()

            else:

                st.error(
                    "Username या password गलत है।"
                )

    with tab2:

        new_username = st.text_input(
            "Username",
            key="signup_username"
        )

        new_name = st.text_input(
            "आपका नाम",
            key="signup_name"
        )

        new_password = st.text_input(
            "Password",
            type="password",
            key="signup_password"
        )

        if st.button(
            "Create Account",
            use_container_width=True
        ):

            ok, message = create_user(
                new_username,
                new_name,
                new_password
            )

            if ok:
                st.success(message)
            else:
                st.error(message)

    with tab3:

        st.write(
            "Guest mode में आप basic AI features try कर सकते हैं।"
        )

        if st.button(
            "Continue as Guest",
            use_container_width=True
        ):

            st.session_state.logged_in = True
            st.session_state.username = "guest"
            st.session_state.name = "Guest"
            st.session_state.plan = "GUEST"

            st.session_state.conversation_id = (
                create_conversation(
                    "guest"
                )
            )

            st.rerun()

    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        f"""
        <div style="font-size:25px;font-weight:800;">
            ✨ जुगनू AI
        </div>
        <div class="jugnu-small">
            आपका अपना AI Assistant
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    st.markdown(
        f"""
        <div class="vip-box">
            <b>👤 {st.session_state.name}</b><br>
            <span class="jugnu-small">
                @{st.session_state.username}
            </span><br><br>
            <b>Plan:</b> {st.session_state.plan}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")

    if st.button(
        "➕ New Chat",
        use_container_width=True
    ):

        st.session_state.conversation_id = (
            create_conversation(
                st.session_state.username
            )
        )

        st.rerun()

    if st.button(
        "🗑️ Delete Current Chat",
        use_container_width=True
    ):

        if st.session_state.conversation_id:

            delete_conversation(
                st.session_state.conversation_id
            )

            st.session_state.conversation_id = (
                create_conversation(
                    st.session_state.username
                )
            )

            st.rerun()

    st.divider()

    st.subheader("💬 Chat History")

    conversations = get_conversations(
        st.session_state.username
    )

    for conversation in conversations[:15]:

        title = conversation["title"]

        if len(title) > 28:
            title = title[:28] + "..."

        if st.button(
            f"💬 {title}",
            key=f"conversation_{conversation['id']}",
            use_container_width=True
        ):

            st.session_state.conversation_id = (
                conversation["id"]
            )

            st.rerun()

    st.divider()

    page = st.radio(
        "Menu",
        [
            "💬 Chat",
            "🎨 AI Image Generator",
            "📄 PDF / Text Reader",
            "🧠 Memory",
            "⚙️ Settings",
            "👑 VIP Dashboard"
        ]
    )

    st.divider()

    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.name = ""
        st.session_state.plan = ""
        st.session_state.conversation_id = None

        st.rerun()


# =========================================================
# MAIN HEADER
# =========================================================

st.markdown(
    f"""
    <div>
        <div class="jugnu-title">✨ जुगनू AI</div>
        <div class="jugnu-subtitle">
            नमस्ते {st.session_state.name} 👋
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")


# =========================================================
# CHAT PAGE
# =========================================================

if page == "💬 Chat":

    st.markdown(
        """
        <div class="jugnu-card">
        <b>जुगनू AI से कुछ भी पूछें</b><br>
        <span class="jugnu-small">
        सवाल पूछें, PDF पढ़वाएँ, web search करें,
        image बनवाएँ या voice से बात करें।
        </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------------------------------
    # Current messages
    # -----------------------------------------------------

    if st.session_state.conversation_id:

        messages = get_messages(
            st.session_state.conversation_id
        )

        for message in messages:

            role = message["role"]
            content = message["content"]

            if role == "user":

                st.markdown(
                    f"""
                    <div class="jugnu-user">
                    <b>आप</b><br>
                    {escape_text(content)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    f"""
                    <div class="jugnu-ai">
                    <b>✨ जुगनू AI</b><br>
                    {escape_text(content)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    st.divider()

    # -----------------------------------------------------
    # Quick actions
    # -----------------------------------------------------

    st.markdown("### ⚡ Quick Actions")

    q1, q2, q3, q4 = st.columns(4)

    with q1:

        if st.button(
            "🎨 Image",
            use_container_width=True
        ):

            st.session_state.quick_prompt = (
                "एक सुंदर राजस्थान के रेगिस्तान में "
                "सूर्यास्त की realistic image बनाओ"
            )

    with q2:

        if st.button(
            "🌐 Web Search",
            use_container_width=True
        ):

            st.session_state.quick_prompt = (
                "आज की latest important news बताओ"
            )

    with q3:

        if st.button(
            "💡 Idea",
            use_container_width=True
        ):

            st.session_state.quick_prompt = (
                "मुझे एक नया business idea बताओ"
            )

    with q4:

        if st.button(
            "📚 Study",
            use_container_width=True
        ):

            st.session_state.quick_prompt = (
                "मुझे पढ़ाई के लिए एक simple study plan बनाओ"
            )

    # -----------------------------------------------------
    # Voice input
    # -----------------------------------------------------

    st.markdown("### 🎤 Voice Input")

    audio_file = st.file_uploader(
        "अपनी voice recording upload करें",
        type=[
            "wav",
            "mp3",
            "m4a",
            "ogg",
            "webm"
        ],
        key="chat_audio"
    )

    voice_prompt = ""

    if audio_file:

        if st.button(
            "🎤 Voice को Text में बदलें"
        ):

            with st.spinner(
                "Voice समझी जा रही है..."
            ):

                voice_prompt, error = (
                    transcribe_audio(
                        audio_file
                    )
                )

            if error:

                st.error(error)

            else:

                st.success(
                    f"आपने कहा: {voice_prompt}"
                )

                st.session_state.quick_prompt = (
                    voice_prompt
                )

    # -----------------------------------------------------
    # File upload
    # -----------------------------------------------------

    uploaded_chat_file = st.file_uploader(
        "📎 PDF / TXT attach करें",
        type=[
            "pdf",
            "txt"
        ],
        key="chat_document"
    )

    if uploaded_chat_file:

        if uploaded_chat_file.name != (
            st.session_state.uploaded_file_name
        ):

            if uploaded_chat_file.name.lower().endswith(
                ".pdf"
            ):

                text = extract_pdf_text(
                    uploaded_chat_file
                )

            else:

                text = extract_text_file(
                    uploaded_chat_file
                )

            st.session_state.pdf_context = text
            st.session_state.uploaded_file_name = (
                uploaded_chat_file.name
            )

        st.success(
            f"📄 {uploaded_chat_file.name} तैयार है।"
        )

    # -----------------------------------------------------
    # Chat input
    # -----------------------------------------------------

    default_prompt = st.session_state.pop(
        "quick_prompt",
        ""
    )

    user_prompt = st.chat_input(
        "जुगनू से कुछ पूछें..."
    )

    if not user_prompt and default_prompt:

        user_prompt = default_prompt

    if user_prompt:

        user_prompt = user_prompt.strip()

        if not st.session_state.conversation_id:

            st.session_state.conversation_id = (
                create_conversation(
                    st.session_state.username
                )
            )

        save_message(
            st.session_state.conversation_id,
            st.session_state.username,
            "user",
            user_prompt
        )

        # -------------------------------------------------
        # IMAGE GENERATION
        # -------------------------------------------------

        if is_image_request(user_prompt):

            st.markdown(
                f"""
                <div class="jugnu-user">
                <b>आप</b><br>
                {escape_text(user_prompt)}
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.spinner(
                "🎨 Gemini image बना रहा है..."
            ):

                image, error = (
                    generate_image_with_gemini(
                        user_prompt
                    )
                )

            if error:

                st.error(
                    f"Image generation में समस्या आई:\n\n{error}"
                )

            elif image:

                st.markdown(
                    "### 🎨 आपकी AI Image"
                )

                st.image(
                    image,
                    use_container_width=True
                )

                # Save image into bytes for download
                image_buffer = io.BytesIO()

                image.save(
                    image_buffer,
                    format="JPEG",
                    quality=95
                )

                image_bytes = image_buffer.getvalue()

                st.download_button(
                    "⬇️ Download Image",
                    data=image_bytes,
                    file_name="jugnu_ai_image.jpg",
                    mime="image/jpeg",
                    use_container_width=True
                )

                st.session_state.last_generated_image = (
                    image_bytes
                )

                st.session_state.last_generated_prompt = (
                    user_prompt
                )

            st.stop()

        # -------------------------------------------------
        # CREATOR ANSWER
        # -------------------------------------------------

        special = creator_answer(
            user_prompt
        )

        if special:

            answer = special

        else:

            # -------------------------------------------------
            # WEB SEARCH
            # -------------------------------------------------

            web_context = ""

            search_words = [
                "latest",
                "today",
                "news",
                "weather",
                "price",
                "current",
                "आज",
                "ताजा",
                "लेटेस्ट",
                "कीमत",
                "मौसम"
            ]

            should_search = any(
                word in user_prompt.lower()
                for word in search_words
            )

            if should_search:

                with st.spinner(
                    "🌐 Web search हो रही है..."
                ):

                    web_context = web_search(
                        user_prompt
                    )

            # -------------------------------------------------
            # HISTORY
            # -------------------------------------------------

            old_messages = get_messages(
                st.session_state.conversation_id
            )

            history = []

            for item in old_messages:

                history.append(
                    {
                        "role": item["role"],
                        "content": item["content"]
                    }
                )

            settings = get_settings(
                st.session_state.username
            )

            answer = ask_groq(
                user_prompt,
                history,
                st.session_state.username,
                settings["language"],
                settings["bot_mode"],
                st.session_state.pdf_context,
                web_context
            )

        save_message(
            st.session_state.conversation_id,
            st.session_state.username,
            "assistant",
            answer
        )

        # First question becomes chat title
        current_messages = get_messages(
            st.session_state.conversation_id
        )

        if len(current_messages) <= 2:

            update_conversation_title(
                st.session_state.conversation_id,
                user_prompt
            )

        st.rerun()


# =========================================================
# IMAGE GENERATOR PAGE
# =========================================================

elif page == "🎨 AI Image Generator":

    st.header("🎨 AI Image Generator")

    st.write(
        "Gemini AI से अपनी पसंद की image बनाइए।"
    )

    prompt = st.text_area(
        "Image के बारे में लिखें",
        height=130,
        placeholder=(
            "उदाहरण: राजस्थान के रेगिस्तान में "
            "एक शानदार sunset, cinematic realistic photography"
        )
    )

    c1, c2 = st.columns(2)

    with c1:

        aspect = st.selectbox(
            "Aspect Ratio",
            [
                "1:1",
                "16:9",
                "9:16",
                "4:3",
                "3:4"
            ]
        )

    with c2:

        style = st.selectbox(
            "Style",
            [
                "Realistic",
                "Cinematic",
                "Anime",
                "Digital Art",
                "3D",
                "Painting",
                "Professional Photography"
            ]
        )

    if st.button(
        "✨ Generate Image",
        type="primary",
        use_container_width=True
    ):

        if not prompt.strip():

            st.warning(
                "पहले image का prompt लिखें।"
            )

        else:

            final_prompt = (
                f"{prompt}\n\n"
                f"Style: {style}\n"
                f"Aspect ratio: {aspect}\n"
                "Create a high quality detailed image."
            )

            with st.spinner(
                "🎨 Gemini image बना रहा है..."
            ):

                image, error = (
                    generate_image_with_gemini(
                        final_prompt
                    )
                )

            if error:

                st.error(
                    f"Image generation में समस्या आई:\n\n{error}"
                )

            elif image:

                st.image(
                    image,
                    use_container_width=True
                )

                image_buffer = io.BytesIO()

                image.save(
                    image_buffer,
                    format="JPEG",
                    quality=95
                )

                image_bytes = image_buffer.getvalue()

                st.download_button(
                    "⬇️ Download Image",
                    data=image_bytes,
                    file_name="jugnu_generated_image.jpg",
                    mime="image/jpeg",
                    use_container_width=True
                )


# =========================================================
# PDF / TEXT READER
# =========================================================

elif page == "📄 PDF / Text Reader":

    st.header("📄 PDF / Text Reader")

    st.write(
        "PDF या TXT file upload करके उसका text पढ़ें।"
    )

    file = st.file_uploader(
        "File upload करें",
        type=[
            "pdf",
            "txt"
        ],
        key="reader_file"
    )

    if file:

        if file.name.lower().endswith(".pdf"):

            text = extract_pdf_text(file)

        else:

            text = extract_text_file(file)

        if text:

            st.success(
                f"{file.name} पढ़ ली गई।"
            )

            st.text_area(
                "Extracted Text",
                text,
                height=450
            )

            st.session_state.pdf_context = text

            st.info(
                "अब Chat में इस document के बारे में सवाल पूछ सकते हैं।"
            )

        else:

            st.warning(
                "इस file से text नहीं मिला।"
            )


# =========================================================
# MEMORY
# =========================================================

elif page == "🧠 Memory":

    st.header("🧠 जुगनू की Memory")

    st.write(
        "यहाँ ऐसी बातें save कर सकते हैं जिन्हें "
        "जुगनू future chats में उपयोग कर सके।"
    )

    memory = st.text_area(
        "क्या याद रखना है?",
        placeholder=(
            "उदाहरण: मुझे हमेशा आसान हिंदी में जवाब चाहिए।"
        )
    )

    if st.button(
        "💾 Memory Save करें",
        use_container_width=True
    ):

        if memory.strip():

            add_memory(
                st.session_state.username,
                memory
            )

            st.success(
                "Memory save हो गई।"
            )

            st.rerun()

        else:

            st.warning(
                "पहले कुछ लिखें।"
            )

    st.divider()

    st.subheader("Saved Memories")

    memories = get_memories(
        st.session_state.username
    )

    if memories:

        for item in memories:

            st.markdown(
                f"""
                <div class="jugnu-card">
                🧠 {escape_text(item["memory"])}
                <div class="jugnu-small">
                {item["created_at"]}
                </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    else:

        st.info(
            "अभी कोई memory save नहीं है।"
        )


# =========================================================
# SETTINGS
# =========================================================

elif page == "⚙️ Settings":

    st.header("⚙️ Settings")

    settings = get_settings(
        st.session_state.username
    )

    language = st.selectbox(
        "Language",
        [
            "Hindi",
            "Hinglish",
            "English"
        ],
        index=[
            "Hindi",
            "Hinglish",
            "English"
        ].index(
            settings["language"]
        )
        if settings["language"] in [
            "Hindi",
            "Hinglish",
            "English"
        ]
        else 0
    )

    bot_mode = st.selectbox(
        "Bot Mode",
        [
            "Smart",
            "Friendly",
            "Professional",
            "Short Answers"
        ],
        index=[
            "Smart",
            "Friendly",
            "Professional",
            "Short Answers"
        ].index(
            settings["bot_mode"]
        )
        if settings["bot_mode"] in [
            "Smart",
            "Friendly",
            "Professional",
            "Short Answers"
        ]
        else 0
    )

    voice_speed = st.slider(
        "Voice Speed",
        1,
        2,
        int(settings["voice_speed"])
    )

    if st.button(
        "💾 Save Settings",
        use_container_width=True
    ):

        save_settings(
            st.session_state.username,
            language,
            bot_mode,
            voice_speed
        )

        st.success(
            "Settings save हो गई।"
        )

    st.divider()

    st.subheader("🔐 Change Password")

    old_password = st.text_input(
        "Old Password",
        type="password"
    )

    new_password = st.text_input(
        "New Password",
        type="password"
    )

    confirm_password = st.text_input(
        "Confirm New Password",
        type="password"
    )

    if st.button(
        "Change Password",
        use_container_width=True
    ):

        if new_password != confirm_password:

            st.error(
                "New password और confirm password अलग हैं।"
            )

        else:

            ok, message = change_password(
                st.session_state.username,
                old_password,
                new_password
            )

            if ok:
                st.success(message)
            else:
                st.error(message)

    st.divider()

    st.subheader("ℹ️ About Jugnu AI")

    st.markdown(
        """
        **जुगनू AI**

        आपका अपना AI Assistant.

        Features:
        - AI Chat
        - Gemini AI Image Generation
        - Voice Input
        - Voice Response
        - PDF Reader
        - Text Reader
        - Web Search
        - Memory
        - Chat History
        - Login / Signup
        - Settings
        """
    )

    st.markdown(
        """
        <div class="creator-box">
        <b>निर्माता</b><br><br>
        Arvind Singh<br>
        Father: Mr Rewant Singh<br>
        Village: Doojasar<br>
        Current: Shri Mohangarh
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# VIP DASHBOARD
# =========================================================

elif page == "👑 VIP Dashboard":

    st.header("👑 VIP Dashboard")

    st.markdown(
        f"""
        <div class="vip-box">
            <h3>✨ {st.session_state.name}</h3>
            <b>Username:</b> @{st.session_state.username}<br>
            <b>Plan:</b> {st.session_state.plan}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")

    col1, col2, col3 = st.columns(3)

    conversations = get_conversations(
        st.session_state.username
    )

    memories = get_memories(
        st.session_state.username
    )

    with col1:

        st.metric(
            "💬 Chats",
            len(conversations)
        )

    with col2:

        st.metric(
            "🧠 Memories",
            len(memories)
        )

    with col3:

        st.metric(
            "👑 Plan",
            st.session_state.plan
        )

    st.divider()

    st.subheader("🚀 Available Features")

    features = [
        "✅ AI Chat",
        "✅ Gemini AI Image Generation",
        "✅ Voice Input",
        "✅ PDF / TXT Reading",
        "✅ Web Search",
        "✅ Memory",
        "✅ Chat History",
        "✅ Login / Signup",
        "✅ Settings",
        "✅ Password Change"
    ]

    for feature in features:

        st.write(feature)


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.markdown(
    """
    <div style="text-align:center;color:#888;font-size:13px;">
        ✨ जुगनू AI — आपका अपना AI Assistant
    </div>
    """,
    unsafe_allow_html=True
)
