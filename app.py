import os
import re
import io
import base64
import hashlib
import sqlite3
from datetime import datetime

import streamlit as st
from groq import Groq
from gtts import gTTS
from pypdf import PdfReader
from PIL import Image

# =========================================================
# OPTIONAL WEB SEARCH
# =========================================================

try:
    from ddgs import DDGS
except Exception:
    try:
        from duckduckgo_search import DDGS
    except Exception:
        DDGS = None


# =========================================================
# GEMINI
# =========================================================

try:
    from google import genai
except Exception:
    genai = None


# =========================================================
# COOKIES
# =========================================================

try:
    from streamlit_cookies_manager_ext import EncryptedCookieManager
except Exception:
    EncryptedCookieManager = None


# =========================================================
# APP SETTINGS
# =========================================================

APP_NAME = "जुगनू AI"

DB_FILE = "jugnu_data.db"

DEFAULT_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

WHISPER_MODEL = "whisper-large-v3-turbo"

# Gemini image generation model
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="जुगनू AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
<style>

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    visibility: hidden;
}

.stApp {
    background: #f7f7f8;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 5rem;
    max-width: 1200px;
}

[data-testid="stSidebar"] {
    background: #202123;
}

[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

.jugnu-title {
    font-size: 32px;
    font-weight: 700;
    text-align: center;
    margin-top: 10px;
    margin-bottom: 5px;
}

.jugnu-subtitle {
    text-align: center;
    color: #777;
    margin-bottom: 25px;
}

.user-card {
    padding: 14px;
    border-radius: 12px;
    background: rgba(255,255,255,0.08);
    margin-bottom: 15px;
}

.creator-card {
    padding: 12px;
    border-radius: 12px;
    background: rgba(255,255,255,0.08);
    font-size: 13px;
    margin-top: 15px;
}

.tool-card {
    padding: 15px;
    border-radius: 15px;
    background: white;
    border: 1px solid #e5e5e5;
    margin-bottom: 15px;
}

.small-text {
    font-size: 12px;
    color: #777;
}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# DATABASE
# =========================================================

def get_db():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name TEXT,
            plan TEXT DEFAULT 'FREE',
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_users (
            username TEXT PRIMARY KEY,
            name TEXT,
            password_hash TEXT,
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
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
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
            task TEXT,
            remind_at TEXT,
            done INTEGER DEFAULT 0,
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
            language TEXT,
            bot_mode TEXT,
            voice_speed TEXT
        )
        """
    )

    conn.commit()

    # =====================================================
    # DEFAULT ARVIND ACCOUNT
    # =====================================================

    username = "arvind"
    name = "अरविंद सिंह"
    password = "Jugnu@123"

    password_hash = hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()

    cur.execute(
        """
        INSERT OR IGNORE INTO users
        (username, name, plan, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            name,
            "VIP PRO",
            datetime.now().isoformat(),
        ),
    )

    cur.execute(
        """
        INSERT OR IGNORE INTO auth_users
        (username, name, password_hash, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            name,
            password_hash,
            datetime.now().isoformat(),
        ),
    )

    cur.execute(
        """
        INSERT OR IGNORE INTO app_settings
        (username, language, bot_mode, voice_speed)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            "Hindi",
            "दोस्ताना",
            "सामान्य",
        ),
    )

    conn.commit()

    conn.close()


init_db()


# =========================================================
# SECRETS
# =========================================================

def get_secret(name):

    try:

        value = st.secrets.get(name)

        if value:
            return value

    except Exception:
        pass

    return os.getenv(name)


def get_groq_key():

    return get_secret("GROQ_API_KEY")


def get_gemini_key():

    return get_secret("GEMINI_API_KEY")


# =========================================================
# PERSISTENT LOGIN COOKIE
# =========================================================

COOKIE_PASSWORD = get_secret("COOKIE_PASSWORD")

# Fallback ताकि app पूरी तरह बंद न हो,
# लेकिन Streamlit Cloud में COOKIE_PASSWORD Secret रखना बेहतर है।
if not COOKIE_PASSWORD:

    COOKIE_PASSWORD = (
        "JugnuAI_Default_Cookie_Secret_2026_ChangeThis"
    )


cookies = None

if EncryptedCookieManager is not None:

    try:

        cookies = EncryptedCookieManager(
            prefix="jugnu_ai/",
            password=COOKIE_PASSWORD,
        )

        if not cookies.ready():

            st.stop()

    except Exception:

        cookies = None


# =========================================================
# LOGIN COOKIE FUNCTIONS
# =========================================================

def save_login_cookie(username):

    if cookies is None:
        return

    try:

        cookies["jugnu_username"] = username

        cookies.save()

    except Exception:

        pass


def get_login_cookie():

    if cookies is None:
        return None

    try:

        username = cookies.get(
            "jugnu_username"
        )

        if username:

            return str(username).strip().lower()

    except Exception:

        pass

    return None


def clear_login_cookie():

    if cookies is None:
        return

    try:

        if "jugnu_username" in cookies:

            del cookies["jugnu_username"]

        cookies.save()

    except Exception:

        pass


# =========================================================
# PASSWORD
# =========================================================

def hash_password(password):

    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


# =========================================================
# USER FUNCTIONS
# =========================================================

def get_user(username):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username=?
        """,
        (username,),
    ).fetchone()

    conn.close()

    return row


def create_user(
    username,
    name,
    password
):

    conn = get_db()

    try:

        password_hash = hash_password(
            password
        )

        conn.execute(
            """
            INSERT INTO users
            (username, name, plan, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                name,
                "FREE",
                datetime.now().isoformat(),
            ),
        )

        conn.execute(
            """
            INSERT INTO auth_users
            (username, name, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                name,
                password_hash,
                datetime.now().isoformat(),
            ),
        )

        conn.execute(
            """
            INSERT INTO app_settings
            (username, language, bot_mode, voice_speed)
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                "Hindi",
                "दोस्ताना",
                "सामान्य",
            ),
        )

        conn.commit()

        return True, "Account created"

    except sqlite3.IntegrityError:

        return False, "Username already exists"

    finally:

        conn.close()


def authenticate(
    username,
    password
):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM auth_users
        WHERE username=?
        """,
        (username,),
    ).fetchone()

    conn.close()

    if not row:

        return False

    return (
        row["password_hash"]
        == hash_password(password)
    )


# =========================================================
# SETTINGS
# =========================================================

def get_settings(username):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM app_settings
        WHERE username=?
        """,
        (username,),
    ).fetchone()

    conn.close()

    if not row:

        return {
            "language": "Hindi",
            "bot_mode": "दोस्ताना",
            "voice_speed": "सामान्य",
        }

    return dict(row)


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
            voice_speed,
        ),
    )

    conn.commit()

    conn.close()


# =========================================================
# CONVERSATIONS
# =========================================================

def create_conversation(
    username,
    title="नई बातचीत"
):

    conn = get_db()

    now = datetime.now().isoformat()

    cur = conn.execute(
        """
        INSERT INTO conversations
        (username, title, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            title,
            now,
            now,
        ),
    )

    conversation_id = cur.lastrowid

    conn.commit()

    conn.close()

    return conversation_id


def get_conversations(username):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM conversations
        WHERE username=?
        ORDER BY updated_at DESC
        """,
        (username,),
    ).fetchall()

    conn.close()

    return rows


def load_messages(conversation_id):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT role, content, created_at
        FROM messages
        WHERE conversation_id=?
        ORDER BY id
        """,
        (conversation_id,),
    ).fetchall()

    conn.close()

    return [
        {
            "role": row["role"],
            "content": row["content"],
        }
        for row in rows
    ]


def save_message(
    conversation_id,
    role,
    content
):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO messages
        (conversation_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            role,
            content,
            datetime.now().isoformat(),
        ),
    )

    conn.execute(
        """
        UPDATE conversations
        SET updated_at=?
        WHERE id=?
        """,
        (
            datetime.now().isoformat(),
            conversation_id,
        ),
    )

    conn.commit()

    conn.close()


def delete_conversation(
    conversation_id
):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM messages
        WHERE conversation_id=?
        """,
        (conversation_id,),
    )

    conn.execute(
        """
        DELETE FROM conversations
        WHERE id=?
        """,
        (conversation_id,),
    )

    conn.commit()

    conn.close()


# =========================================================
# MEMORY
# =========================================================

def get_memories(username):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT memory
        FROM user_memories
        WHERE username=?
        ORDER BY id DESC
        LIMIT 20
        """,
        (username,),
    ).fetchall()

    conn.close()

    return [
        row["memory"]
        for row in rows
    ]


def save_memory(
    username,
    memory
):

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
            datetime.now().isoformat(),
        ),
    )

    conn.commit()

    conn.close()


def delete_memory(
    username,
    memory
):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM user_memories
        WHERE username=?
        AND memory=?
        """,
        (
            username,
            memory,
        ),
    )

    conn.commit()

    conn.close()


# =========================================================
# REMINDERS
# =========================================================

def save_note(
    username,
    task,
    remind_at
):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO notes
        (username, task, remind_at, done, created_at)
        VALUES (?, ?, ?, 0, ?)
        """,
        (
            username,
            task,
            remind_at,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()

    conn.close()


def get_notes(username):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM notes
        WHERE username=?
        ORDER BY id DESC
        """,
        (username,),
    ).fetchall()

    conn.close()

    return rows


def mark_note_done(note_id):

    conn = get_db()

    conn.execute(
        """
        UPDATE notes
        SET done=1
        WHERE id=?
        """,
        (note_id,),
    )

    conn.commit()

    conn.close()


# =========================================================
# GROQ CLIENT
# =========================================================

def get_groq_client():

    key = get_groq_key()

    if not key:

        return None

    try:

        return Groq(
            api_key=key
        )

    except Exception:

        return None


# =========================================================
# GEMINI CLIENT
# =========================================================

def get_gemini_client():

    key = get_gemini_key()

    if not key:

        return None

    if genai is None:

        return None

    try:

        return genai.Client(
            api_key=key
        )

    except Exception:

        return None


# =========================================================
# GEMINI IMAGE GENERATION
# =========================================================

def generate_gemini_image(prompt):

    key = get_gemini_key()

    if not key:

        return None, (
            "❌ GEMINI_API_KEY नहीं मिली।\n\n"
            "Streamlit Cloud → Manage app → Settings → Secrets "
            "में GEMINI_API_KEY डालें।"
        )

    if genai is None:

        return None, (
            "❌ google-genai package install नहीं है।\n\n"
            "requirements.txt में "
            "`google-genai` जोड़ें।"
        )

    try:

        client = genai.Client(
            api_key=key
        )

        interaction = client.interactions.create(
            model=GEMINI_IMAGE_MODEL,
            input=prompt,
            response_format={
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": "1:1",
                "image_size": "1K",
            },
        )

        # ---------------------------------------------
        # Main output_image
        # ---------------------------------------------

        if interaction.output_image:

            image_data = (
                interaction
                .output_image
                .data
            )

            if image_data:

                return (
                    base64.b64decode(
                        image_data
                    ),
                    None,
                )

        # ---------------------------------------------
        # Fallback: inspect steps
        # ---------------------------------------------

        try:

            for step in interaction.steps:

                if getattr(
                    step,
                    "type",
                    None
                ) != "model_output":

                    continue

                content_blocks = getattr(
                    step,
                    "content",
                    []
                )

                for block in content_blocks:

                    if getattr(
                        block,
                        "type",
                        None
                    ) == "image":

                        data = getattr(
                            block,
                            "data",
                            None
                        )

                        if data:

                            return (
                                base64.b64decode(
                                    data
                                ),
                                None,
                            )

        except Exception:

            pass

        return None, (
            "❌ Gemini ने image data वापस नहीं दिया।\n\n"
            "कृपया दूसरा prompt try करें।"
        )

    except Exception as e:

        error_text = str(e)

        if (
            "401" in error_text
            or "UNAUTHENTICATED"
            in error_text
            or "ACCESS_TOKEN_TYPE_UNSUPPORTED"
            in error_text
        ):

            return None, (
                "❌ Gemini authentication error आया।\n\n"
                "कृपया सुनिश्चित करें कि "
                "`GEMINI_API_KEY` में Google AI Studio की "
                "Gemini API key लगी है।\n\n"
                "OAuth access token या Google login token "
                "यहाँ नहीं लगाना है।"
            )

        return None, (
            "❌ Image generation में समस्या आई:\n\n"
            + error_text
        )


# =========================================================
# IMAGE REQUEST DETECTION
# =========================================================

def photo_request(text):

    text = text.lower().strip()

    patterns = [

        "photo बनाओ",
        "फोटो बनाओ",
        "फोटो बना",
        "फोटो बनाइए",

        "image बनाओ",
        "इमेज बनाओ",
        "चित्र बनाओ",
        "तस्वीर बनाओ",

        "photo banao",
        "photo bana",

        "image banao",
        "image bana",

        "generate image",
        "generate photo",

        "create image",
        "create a image",
        "create a picture",

        "make an image",
        "make image",
        "make a picture",

        "generate a picture",

        "draw an image",
        "draw a picture",

        "ai image",
        "ai photo",
        "ai picture",
    ]

    return any(
        phrase in text
        for phrase in patterns
    )


def clean_image_prompt(text):

    replacements = [

        "फोटो बनाओ",
        "फोटो बना",
        "फोटो बनाइए",
        "फोटो तैयार करो",

        "image बनाओ",
        "इमेज बनाओ",
        "चित्र बनाओ",
        "तस्वीर बनाओ",

        "photo banao",
        "photo bana",

        "image banao",
        "image bana",

        "generate image",
        "generate photo",
        "generate a picture",

        "create image",
        "create a image",
        "create a picture",

        "make an image",
        "make image",
        "make a picture",
    ]

    prompt = text

    for item in replacements:

        prompt = re.sub(
            re.escape(item),
            "",
            prompt,
            flags=re.IGNORECASE,
        )

    prompt = prompt.strip()

    if not prompt:

        prompt = (
            "Create a beautiful cinematic realistic image "
            "with detailed lighting and professional photography."
        )

    return prompt


# =========================================================
# WEB SEARCH
# =========================================================

def likely_needs_search(text):

    text = text.lower()

    words = [

        "आज",
        "अभी",
        "latest",
        "news",
        "ताजा खबर",

        "weather",
        "मौसम",

        "price",
        "कीमत",

        "rate",
        "रेट",

        "कौन जीता",
        "result",
        "नतीजा",

        "current",
        "live",
    ]

    return any(
        word in text
        for word in words
    )


def web_search(
    query,
    max_results=5
):

    if DDGS is None:

        return ""

    try:

        results = []

        with DDGS() as ddgs:

            data = ddgs.text(
                query,
                max_results=max_results,
            )

            for item in data:

                title = item.get(
                    "title",
                    ""
                )

                body = item.get(
                    "body",
                    ""
                )

                href = item.get(
                    "href",
                    ""
                )

                results.append(
                    f"Title: {title}\n"
                    f"Summary: {body}\n"
                    f"URL: {href}"
                )

        return "\n\n".join(
            results
        )

    except Exception:

        return ""


# =========================================================
# PDF
# =========================================================

def extract_pdf_text(
    uploaded_file
):

    try:

        reader = PdfReader(
            uploaded_file
        )

        pages = []

        for page in reader.pages:

            text = page.extract_text()

            if text:

                pages.append(text)

        return "\n\n".join(
            pages
        )

    except Exception as e:

        return (
            f"PDF पढ़ने में समस्या: {e}"
        )


# =========================================================
# TXT
# =========================================================

def extract_txt_text(
    uploaded_file
):

    try:

        return uploaded_file.read().decode(
            "utf-8",
            errors="ignore",
        )

    except Exception as e:

        return (
            f"TXT पढ़ने में समस्या: {e}"
        )


# =========================================================
# VOICE TRANSCRIPTION
# =========================================================

def transcribe_audio(
    audio_file
):

    client = get_groq_client()

    if client is None:

        return (
            "❌ Voice transcription के लिए "
            "GROQ_API_KEY जरूरी है।"
        )

    try:

        audio_bytes = (
            audio_file.read()
        )

        file_tuple = (
            "audio.wav",
            audio_bytes,
        )

        transcription = (
            client.audio.transcriptions.create(
                file=file_tuple,
                model=WHISPER_MODEL,
            )
        )

        return transcription.text

    except Exception as e:

        return (
            f"❌ Voice error: {e}"
        )


# =========================================================
# TEXT TO SPEECH
# =========================================================

def make_tts(
    text,
    language="hi"
):

    try:

        output = io.BytesIO()

        tts = gTTS(
            text=text,
            lang=language,
            slow=False,
        )

        tts.write_to_fp(
            output
        )

        output.seek(0)

        return output

    except Exception:

        return None


# =========================================================
# CREATOR
# =========================================================

def creator_answer():

    return (
        "✨ जुगनू AI के निर्माता "
        "**अरविंद सिंह** हैं।\n\n"
        "👨‍👦 उनके पिता का नाम "
        "**Mr Rewant Singh** है।\n"
        "🏡 उनका गाँव **Doojasar** है।\n"
        "📍 वे अभी **श्री मोहनगढ़** में रहते हैं।"
    )


def is_creator_question(text):

    text = text.lower()

    words = [

        "jugnu ai kisne banaya",
        "jugnu kisne banaya",
        "jugnu ai creator",
        "creator of jugnu",
        "who created jugnu",

        "जुगनू ai किसने बनाया",
        "जुगनू किसने बनाया",
        "जुगनू का निर्माता",
        "जुगनू ai का निर्माता",
        "जुगनू एआई किसने बनाया",
        "निर्माता कौन है",
    ]

    return any(
        item in text
        for item in words
    )


# =========================================================
# SYSTEM PROMPT
# =========================================================

def build_system_prompt(
    username,
    language,
    bot_mode,
    memories
):

    memory_text = ""

    if memories:

        memory_text = (
            "\n\nUser memories:\n"
            + "\n".join(
                f"- {m}"
                for m in memories
            )
        )

    language_instruction = {

        "Hindi":
            "मुख्य रूप से हिंदी में जवाब दो।",

        "English":
            "मुख्य रूप से English में जवाब दो।",

        "Hindi + English":
            "Hindi और English दोनों का natural मिश्रण रखो।",

    }.get(
        language,
        "मुख्य रूप से हिंदी में जवाब दो।",
    )

    mode_instruction = {

        "दोस्ताना":
            "दोस्त की तरह friendly और सरल तरीके से जवाब दो।",

        "शिक्षक":
            "teacher की तरह step-by-step और आसान भाषा में समझाओ।",

        "कहानीकार":
            "जरूरत पड़ने पर कहानी जैसे interesting तरीके से समझाओ।",

        "मारवाड़ी / राजस्थानी":
            "जहाँ उचित हो वहाँ राजस्थानी/मारवाड़ी अंदाज में जवाब दो।",

    }.get(
        bot_mode,
        "friendly तरीके से जवाब दो।",
    )

    return f"""
तुम Jugnu AI हो।

तुम्हें हमेशा helpful, natural और साफ जवाब देना है।

{language_instruction}

{mode_instruction}

Jugnu AI के निर्माता:

नाम: Arvind Singh
पिता: Mr Rewant Singh
गाँव: Doojasar
वर्तमान स्थान: Shri Mohangarh

अगर user creator के बारे में पूछे तो उपलब्ध जानकारी के अनुसार सही उत्तर देना।

गलत जानकारी invent मत करना।

अगर user किसी विषय को सरल तरीके से समझना चाहता है
तो आसान भाषा में समझाओ।

User username:
{username}

{memory_text}
"""


# =========================================================
# GROQ CHAT
# =========================================================

def ask_groq(
    user_prompt,
    conversation_messages,
    username,
    language,
    bot_mode,
    memories,
    document_context="",
    web_context=""
):

    client = get_groq_client()

    if client is None:

        return (
            "❌ GROQ_API_KEY नहीं मिली।\n\n"
            "Streamlit Cloud → Settings → Secrets में "
            "`GROQ_API_KEY` डालें।"
        )

    system_prompt = build_system_prompt(
        username,
        language,
        bot_mode,
        memories,
    )

    if document_context:

        system_prompt += (
            "\n\nUser uploaded document content:\n"
            + document_context[:30000]
        )

    if web_context:

        system_prompt += (
            "\n\nWeb search results:\n"
            + web_context[:15000]
        )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    for message in conversation_messages[-12:]:

        role = message.get(
            "role"
        )

        if role not in [
            "user",
            "assistant"
        ]:

            continue

        messages.append(
            {
                "role": role,
                "content": message.get(
                    "content",
                    "",
                ),
            }
        )

    messages.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )

    try:

        response = (
            client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )
        )

        return (
            response
            .choices[0]
            .message
            .content
        )

    except Exception:

        try:

            response = (
                client.chat.completions.create(
                    model=FALLBACK_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                )
            )

            return (
                response
                .choices[0]
                .message
                .content
            )

        except Exception as e:

            return (
                "❌ AI response में समस्या आई:\n\n"
                + str(e)
            )


# =========================================================
# PROCESS PROMPT
# =========================================================

def process_prompt(
    prompt,
    document_context="",
    web_enabled=False
):

    prompt = prompt.strip()

    if not prompt:

        return

    username = (
        st.session_state.username
    )

    conversation_id = (
        st.session_state
        .current_conversation_id
    )

    # -----------------------------------------------------
    # USER MESSAGE SAVE
    # -----------------------------------------------------

    save_message(
        conversation_id,
        "user",
        prompt,
    )

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    # -----------------------------------------------------
    # CREATOR
    # -----------------------------------------------------

    if is_creator_question(
        prompt
    ):

        answer = creator_answer()

        save_message(
            conversation_id,
            "assistant",
            answer,
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        return

    # -----------------------------------------------------
    # IMAGE
    # -----------------------------------------------------

    if photo_request(
        prompt
    ):

        image_prompt = (
            clean_image_prompt(
                prompt
            )
        )

        with st.spinner(
            "🎨 जुगनू AI image बना रहा है..."
        ):

            image_bytes, error = (
                generate_gemini_image(
                    image_prompt
                )
            )

        if error:

            save_message(
                conversation_id,
                "assistant",
                error,
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": error,
                }
            )

        else:

            answer = (
                "🎨 आपकी image तैयार है!\n\n"
                f"Prompt: {image_prompt}"
            )

            save_message(
                conversation_id,
                "assistant",
                answer,
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "image_data": image_bytes,
                    "image_prompt": image_prompt,
                }
            )

        return

    # -----------------------------------------------------
    # WEB
    # -----------------------------------------------------

    web_context = ""

    if (
        web_enabled
        or likely_needs_search(prompt)
    ):

        with st.spinner(
            "🌐 जानकारी खोजी जा रही है..."
        ):

            web_context = web_search(
                prompt
            )

    # -----------------------------------------------------
    # MEMORY
    # -----------------------------------------------------

    memories = get_memories(
        username
    )

    settings = get_settings(
        username
    )

    # -----------------------------------------------------
    # AI
    # -----------------------------------------------------

    with st.spinner(
        "✨ जुगनू सोच रहा है..."
    ):

        answer = ask_groq(
            user_prompt=prompt,
            conversation_messages=(
                st.session_state.messages[:-1]
            ),
            username=username,
            language=settings["language"],
            bot_mode=settings["bot_mode"],
            memories=memories,
            document_context=document_context,
            web_context=web_context,
        )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    save_message(
        conversation_id,
        "assistant",
        answer,
    )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )


# =========================================================
# RENDER MESSAGE
# =========================================================

def render_message(
    message
):

    role = message.get(
        "role"
    )

    content = message.get(
        "content",
        ""
    )

    with st.chat_message(
        role
    ):

        st.markdown(
            content
        )

        if role == "assistant":

            image_data = message.get(
                "image_data"
            )

            if image_data:

                st.image(
                    image_data,
                    use_container_width=True,
                )

                st.download_button(
                    "⬇️ Image डाउनलोड करें",
                    data=image_data,
                    file_name="jugnu_ai_image.jpg",
                    mime="image/jpeg",
                    key="download_"
                    + str(id(message)),
                )


# =========================================================
# LOGIN PAGE
# =========================================================

def login_page():

    st.markdown(
        """
        <div class="jugnu-title">
            ✨ जुगनू AI
        </div>

        <div class="jugnu-subtitle">
            आपका अपना AI Assistant
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(
        [
            "🔐 Login",
            "📝 Signup",
            "👤 Guest",
        ]
    )

    # =====================================================
    # LOGIN
    # =====================================================

    with tab1:

        username = st.text_input(
            "Username",
            key="login_username",
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password",
        )

        if st.button(
            "Login",
            use_container_width=True,
        ):

            username_clean = (
                username.strip().lower()
            )

            if authenticate(
                username_clean,
                password,
            ):

                st.session_state.logged_in = True

                st.session_state.username = (
                    username_clean
                )

                # -----------------------------------------
                # SAVE LOGIN FOR FUTURE VISITS
                # -----------------------------------------

                save_login_cookie(
                    username_clean
                )

                st.rerun()

            else:

                st.error(
                    "Username या password गलत है।"
                )

    # =====================================================
    # SIGNUP
    # =====================================================

    with tab2:

        name = st.text_input(
            "आपका नाम",
            key="signup_name",
        )

        username = st.text_input(
            "Username",
            key="signup_username",
        )

        password = st.text_input(
            "Password",
            type="password",
            key="signup_password",
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            key="signup_confirm",
        )

        if st.button(
            "Account बनाएं",
            use_container_width=True,
        ):

            if (
                not name
                or not username
                or not password
            ):

                st.warning(
                    "सभी fields भरें।"
                )

            elif (
                password
                != confirm_password
            ):

                st.error(
                    "दोनों passwords समान नहीं हैं।"
                )

            else:

                ok, message = (
                    create_user(
                        username.strip().lower(),
                        name.strip(),
                        password,
                    )
                )

                if ok:

                    st.success(
                        "Account बन गया। अब Login करें।"
                    )

                else:

                    st.error(
                        message
                    )

    # =====================================================
    # GUEST
    # =====================================================

    with tab3:

        st.write(
            "बिना account के Jugnu AI इस्तेमाल करें।"
        )

        if st.button(
            "👤 Guest के रूप में जारी रखें",
            use_container_width=True,
        ):

            st.session_state.logged_in = True

            st.session_state.username = (
                "guest"
            )

            st.session_state.current_conversation_id = (
                create_conversation(
                    "guest",
                    "Guest Chat",
                )
            )

            st.session_state.messages = []

            # Guest login persistent नहीं रखा गया है।

            st.rerun()


# =========================================================
# SESSION STATE
# =========================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False


if "username" not in st.session_state:

    st.session_state.username = None


if "current_conversation_id" not in st.session_state:

    st.session_state.current_conversation_id = None


if "messages" not in st.session_state:

    st.session_state.messages = []


if "pending_prompt" not in st.session_state:

    st.session_state.pending_prompt = None


# =========================================================
# RESTORE LOGIN FROM COOKIE
# =========================================================

if not st.session_state.logged_in:

    saved_username = get_login_cookie()

    if saved_username:

        saved_user = get_user(
            saved_username
        )

        if saved_user:

            st.session_state.logged_in = True

            st.session_state.username = (
                saved_username
            )

        else:

            clear_login_cookie()


# =========================================================
# LOGIN CHECK
# =========================================================

if not st.session_state.logged_in:

    login_page()

    st.stop()


# =========================================================
# CURRENT USER
# =========================================================

username = (
    st.session_state.username
)

user = get_user(
    username
)

if user:

    display_name = user["name"]

    plan = user["plan"]

else:

    display_name = "Guest"

    plan = "FREE"


# =========================================================
# FIRST CONVERSATION
# =========================================================

if (
    st.session_state
    .current_conversation_id
    is None
):

    st.session_state.current_conversation_id = (
        create_conversation(
            username,
            "नई बातचीत",
        )
    )

    st.session_state.messages = []


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        "## ✨ जुगनू AI"
    )

    st.markdown(
        f"""
        <div class="user-card">
            <b>👤 {display_name}</b><br>
            <small>@{username}</small><br>
            <small>Plan: {plan}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =====================================================
    # NEW CHAT
    # =====================================================

    if st.button(
        "➕ नई चैट",
        use_container_width=True,
    ):

        st.session_state.current_conversation_id = (
            create_conversation(
                username,
                "नई बातचीत",
            )
        )

        st.session_state.messages = []

        st.rerun()

    st.divider()

    # =====================================================
    # WEB
    # =====================================================

    web_enabled = st.toggle(
        "🌐 Web Search",
        value=False,
    )

    # =====================================================
    # VOICE
    # =====================================================

    voice_response = st.toggle(
        "🔊 Voice Response",
        value=False,
    )

    # =====================================================
    # SETTINGS
    # =====================================================

    with st.expander(
        "⚙️ Settings"
    ):

        settings = get_settings(
            username
        )

        languages = [
            "Hindi",
            "English",
            "Hindi + English",
        ]

        current_language = (
            settings["language"]
            if settings["language"]
            in languages
            else "Hindi"
        )

        language = st.selectbox(
            "Language",
            languages,
            index=languages.index(
                current_language
            ),
        )

        modes = [
            "दोस्ताना",
            "शिक्षक",
            "कहानीकार",
            "मारवाड़ी / राजस्थानी",
        ]

        current_mode = (
            settings["bot_mode"]
            if settings["bot_mode"]
            in modes
            else "दोस्ताना"
        )

        bot_mode = st.selectbox(
            "Bot Mode",
            modes,
            index=modes.index(
                current_mode
            ),
        )

        speeds = [
            "सामान्य",
            "धीमी",
        ]

        current_speed = (
            settings["voice_speed"]
            if settings["voice_speed"]
            in speeds
            else "सामान्य"
        )

        voice_speed = st.selectbox(
            "Voice Speed",
            speeds,
            index=speeds.index(
                current_speed
            ),
        )

        if st.button(
            "💾 Settings Save",
            use_container_width=True,
        ):

            save_settings(
                username,
                language,
                bot_mode,
                voice_speed,
            )

            st.success(
                "Settings save हो गईं।"
            )

        # =================================================
        # PASSWORD
        # =================================================

        st.markdown(
            "### 🔐 Password बदलें"
        )

        old_password = st.text_input(
            "पुराना Password",
            type="password",
            key="old_password",
        )

        new_password = st.text_input(
            "नया Password",
            type="password",
            key="new_password",
        )

        if st.button(
            "Password बदलें",
            use_container_width=True,
        ):

            if authenticate(
                username,
                old_password,
            ):

                conn = get_db()

                conn.execute(
                    """
                    UPDATE auth_users
                    SET password_hash=?
                    WHERE username=?
                    """,
                    (
                        hash_password(
                            new_password
                        ),
                        username,
                    ),
                )

                conn.commit()

                conn.close()

                st.success(
                    "Password बदल गया।"
                )

            else:

                st.error(
                    "पुराना password गलत है।"
                )

        # =================================================
        # DELETE CHAT
        # =================================================

        if st.button(
            "🗑️ Current Chat Delete",
            use_container_width=True,
        ):

            delete_conversation(
                st.session_state
                .current_conversation_id
            )

            st.session_state.current_conversation_id = (
                create_conversation(
                    username,
                    "नई बातचीत",
                )
            )

            st.session_state.messages = []

            st.rerun()

    # =====================================================
    # MEMORY
    # =====================================================

    with st.expander(
        "🧠 Memory"
    ):

        memories = get_memories(
            username
        )

        memory_input = st.text_input(
            "कुछ याद रखना है?",
            placeholder=(
                "जैसे: मुझे हिंदी में जवाब पसंद है"
            ),
        )

        if st.button(
            "Memory Save",
            use_container_width=True,
        ):

            if memory_input.strip():

                save_memory(
                    username,
                    memory_input,
                )

                st.success(
                    "Memory save हो गई।"
                )

                st.rerun()

        if memories:

            st.markdown(
                "### Saved Memories"
            )

            for index, memory in enumerate(
                memories
            ):

                st.write(
                    "• " + memory
                )

                if st.button(
                    "Delete",
                    key=(
                        "memory_"
                        + str(index)
                        + "_"
                        + str(abs(hash(memory)))
                    ),
                ):

                    delete_memory(
                        username,
                        memory,
                    )

                    st.rerun()

    # =====================================================
    # REMINDERS
    # =====================================================

    with st.expander(
        "⏰ Reminders / Diary"
    ):

        task = st.text_input(
            "काम / Reminder",
        )

        remind_at = st.text_input(
            "Date / Time",
            placeholder=(
                "जैसे 10 Oct 2026 10:00"
            ),
        )

        if st.button(
            "Reminder Save",
            use_container_width=True,
        ):

            if task.strip():

                save_note(
                    username,
                    task,
                    remind_at,
                )

                st.success(
                    "Reminder save हो गया।"
                )

                st.rerun()

        notes = get_notes(
            username
        )

        for note in notes:

            status = (
                "✅"
                if note["done"]
                else "⏳"
            )

            st.write(
                f"{status} {note['task']}"
            )

            if note["remind_at"]:

                st.caption(
                    note["remind_at"]
                )

            if not note["done"]:

                if st.button(
                    "Done",
                    key=(
                        "note_"
                        + str(note["id"])
                    ),
                ):

                    mark_note_done(
                        note["id"]
                    )

                    st.rerun()

    # =====================================================
    # CHAT HISTORY
    # =====================================================

    with st.expander(
        "🕘 Chat History"
    ):

        conversations = (
            get_conversations(
                username
            )
        )

        for conversation in conversations[:30]:

            if st.button(
                conversation["title"][:35],
                key=(
                    "conversation_"
                    + str(conversation["id"])
                ),
                use_container_width=True,
            ):

                st.session_state.current_conversation_id = (
                    conversation["id"]
                )

                st.session_state.messages = (
                    load_messages(
                        conversation["id"]
                    )
                )

                st.rerun()

    # =====================================================
    # VIP
    # =====================================================

    with st.expander(
        "👑 VIP Dashboard"
    ):

        st.write(
            "Plan:",
            plan,
        )

        st.write(
            "✨ AI Chat"
        )

        st.write(
            "🎨 Gemini Image Generation"
        )

        st.write(
            "🌐 Web Search"
        )

        st.write(
            "📄 PDF Reading"
        )

        st.write(
            "🎤 Voice Input"
        )

        st.write(
            "🧠 Memory"
        )

    # =====================================================
    # CREATOR
    # =====================================================

    st.markdown(
        """
        <div class="creator-card">
        <b>जुगनू AI निर्माता</b><br><br>
        Arvind Singh<br>
        Father: Mr Rewant Singh<br>
        Village: Doojasar<br>
        Current: Shri Mohangarh
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # =====================================================
    # LOGOUT
    # =====================================================

    if st.button(
        "🚪 Logout",
        use_container_width=True,
    ):

        # ---------------------------------------------
        # REMOVE PERSISTENT LOGIN
        # ---------------------------------------------

        clear_login_cookie()

        st.session_state.logged_in = False

        st.session_state.username = None

        st.session_state.messages = []

        st.session_state.current_conversation_id = None

        st.rerun()


# =========================================================
# MAIN HEADER
# =========================================================

st.markdown(
    """
    <div class="jugnu-title">
        ✨ जुगनू AI
    </div>

    <div class="jugnu-subtitle">
        आपका अपना AI Assistant
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# WELCOME
# =========================================================

if not st.session_state.messages:

    st.markdown(
        f"""
        <div style="
            text-align:center;
            padding:25px;
        ">
            <h2>नमस्ते {display_name}! 👋</h2>
            <p>
            मैं जुगनू AI हूँ।
            आप मुझसे कुछ भी पूछ सकते हैं।
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# QUICK ACTIONS
# =========================================================

st.markdown(
    "### ⚡ Quick Actions"
)

quick_cols = st.columns(4)

quick_actions = [

    (
        "👨‍💻 Creator",
        "जुगनू AI किसने बनाया?"
    ),

    (
        "🕐 Time",
        "अभी समय क्या है?"
    ),

    (
        "🌦️ Weather",
        "आज का मौसम कैसा है?"
    ),

    (
        "🎨 Photo",
        "राजस्थान के रेगिस्तान की cinematic realistic photo बनाओ"
    ),

    (
        "😂 Joke",
        "एक मजेदार joke सुनाओ"
    ),

    (
        "🧠 Quiz",
        "मेरा एक सामान्य ज्ञान quiz लो"
    ),

    (
        "❤️ Health",
        "स्वस्थ रहने के लिए सामान्य tips बताओ"
    ),

    (
        "🏜️ Marwari",
        "मुझसे मारवाड़ी में बात करो"
    ),
]


for index, (
    label,
    quick_prompt
) in enumerate(
    quick_actions
):

    with quick_cols[
        index % 4
    ]:

        if st.button(
            label,
            key=(
                "quick_"
                + str(index)
            ),
            use_container_width=True,
        ):

            process_prompt(
                quick_prompt,
                web_enabled=web_enabled,
            )

            st.rerun()


# =========================================================
# IMAGE GENERATOR
# =========================================================

st.markdown("---")

with st.expander(
    "🎨 AI Image Generator — Gemini"
):

    st.write(
        "Prompt लिखें और जुगनू AI से वास्तविक image बनवाएँ।"
    )

    image_prompt = st.text_area(
        "Image Prompt",
        placeholder=(
            "उदाहरण: राजस्थान के रेगिस्तान में "
            "सूर्यास्त के समय एक शानदार सफेद SUV, "
            "cinematic realistic photography"
        ),
        key="image_generator_prompt",
    )

    image_col1, image_col2 = st.columns(
        [3, 1]
    )

    with image_col2:

        generate_button = st.button(
            "🎨 Generate",
            use_container_width=True,
        )

    if generate_button:

        if not image_prompt.strip():

            st.warning(
                "पहले image prompt लिखें।"
            )

        else:

            with st.spinner(
                "🎨 Gemini image बना रहा है..."
            ):

                image_bytes, error = (
                    generate_gemini_image(
                        image_prompt
                    )
                )

            if error:

                st.error(
                    error
                )

            else:

                st.image(
                    image_bytes,
                    caption="✨ Jugnu AI",
                    use_container_width=True,
                )

                st.download_button(
                    "⬇️ Image Download",
                    data=image_bytes,
                    file_name=(
                        "jugnu_ai_generated.jpg"
                    ),
                    mime="image/jpeg",
                    use_container_width=True,
                )


# =========================================================
# DOCUMENT UPLOAD
# =========================================================

st.markdown("---")

tool_cols = st.columns(3)

document_context = ""

with tool_cols[0]:

    uploaded_document = st.file_uploader(
        "📄 PDF / TXT",
        type=[
            "pdf",
            "txt",
        ],
    )

    if uploaded_document:

        if (
            uploaded_document
            .name
            .lower()
            .endswith(".pdf")
        ):

            document_context = (
                extract_pdf_text(
                    uploaded_document
                )
            )

        else:

            document_context = (
                extract_txt_text(
                    uploaded_document
                )
            )

        st.success(
            "Document तैयार है। अब सवाल पूछें।"
        )


# =========================================================
# IMAGE UPLOAD
# =========================================================

with tool_cols[1]:

    uploaded_image = st.file_uploader(
        "🖼️ Image Upload",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
    )

    if uploaded_image:

        try:

            image = Image.open(
                uploaded_image
            )

            st.image(
                image,
                caption="Uploaded Image",
                use_container_width=True,
            )

        except Exception:

            st.error(
                "Image पढ़ने में समस्या आई।"
            )


# =========================================================
# VOICE INPUT
# =========================================================

with tool_cols[2]:

    audio_file = st.file_uploader(
        "🎤 Voice Input",
        type=[
            "wav",
            "mp3",
            "m4a",
            "ogg",
            "webm",
        ],
    )

    if audio_file:

        if st.button(
            "🎤 Voice को Text में बदलें",
            use_container_width=True,
        ):

            with st.spinner(
                "🎤 Voice समझी जा रही है..."
            ):

                transcribed = (
                    transcribe_audio(
                        audio_file
                    )
                )

            st.session_state.pending_prompt = (
                transcribed
            )

            st.success(
                "Voice text तैयार है। नीचे chat में भेजें।"
            )


# =========================================================
# CHAT HISTORY DISPLAY
# =========================================================

for message in (
    st.session_state.messages
):

    render_message(
        message
    )


# =========================================================
# VOICE TRANSCRIPTION RESULT
# =========================================================

if st.session_state.pending_prompt:

    st.info(
        "🎤 Voice text: "
        + st.session_state.pending_prompt
    )

    if st.button(
        "📤 यह message भेजें"
    ):

        prompt = (
            st.session_state.pending_prompt
        )

        st.session_state.pending_prompt = None

        process_prompt(
            prompt,
            document_context=document_context,
            web_enabled=web_enabled,
        )

        st.rerun()


# =========================================================
# CHAT INPUT
# =========================================================

prompt = st.chat_input(
    "जुगनू से कुछ भी पूछें..."
)


if prompt:

    process_prompt(
        prompt,
        document_context=document_context,
        web_enabled=web_enabled,
    )

    # =====================================================
    # VOICE RESPONSE
    # =====================================================

    if voice_response:

        if st.session_state.messages:

            last_message = (
                st.session_state.messages[-1]
            )

            if (
                last_message["role"]
                == "assistant"
            ):

                answer = (
                    last_message["content"]
                )

                tts_language = "hi"

                settings = get_settings(
                    username
                )

                if (
                    settings["language"]
                    == "English"
                ):

                    tts_language = "en"

                audio = make_tts(
                    answer,
                    tts_language,
                )

                if audio:

                    st.audio(
                        audio,
                        format="audio/mp3",
                    )

    st.rerun()


# =========================================================
# FOOTER
# =========================================================

st.markdown(
    """
    <div style="
        text-align:center;
        color:#888;
        font-size:12px;
        margin-top:40px;
    ">
        ✨ Jugnu AI • Made with ❤️
    </div>
    """,
    unsafe_allow_html=True,
)
