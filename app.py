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
    DDGS_AVAILABLE = True
except Exception:
    DDGS_AVAILABLE = False

# =========================================================
# GEMINI
# =========================================================

try:
    from google import genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

# =========================================================
# PERSISTENT LOGIN COOKIE
# =========================================================

try:
    from streamlit_cookies_manager_ext import EncryptedCookieManager
    COOKIE_AVAILABLE = True
except Exception:
    COOKIE_AVAILABLE = False


# =========================================================
# APP SETTINGS
# =========================================================

APP_NAME = "जुगनू AI"

DB_FILE = "jugnu_data.db"

DEFAULT_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

WHISPER_MODEL = "whisper-large-v3-turbo"

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
        background: #f7f8fc;
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
    }

    .jugnu-title {
        text-align: center;
        font-size: 42px;
        font-weight: 800;
        margin-top: 10px;
        margin-bottom: 0px;
    }

    .jugnu-subtitle {
        text-align: center;
        color: #777;
        font-size: 16px;
        margin-bottom: 25px;
    }

    .chat-user {
        background: #e8f0fe;
        padding: 12px 16px;
        border-radius: 15px;
        margin: 8px 0;
    }

    .chat-ai {
        background: #ffffff;
        padding: 12px 16px;
        border-radius: 15px;
        margin: 8px 0;
        border: 1px solid #eeeeee;
    }

    .creator-box {
        padding: 15px;
        border-radius: 15px;
        background: #fff;
        border: 1px solid #e5e5e5;
    }

    .small-text {
        color: #777;
        font-size: 13px;
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT,
            plan TEXT DEFAULT 'FREE',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS auth_users (
            username TEXT PRIMARY KEY,
            password_hash TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            image_data TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            content TEXT,
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

    # -----------------------------------------------------
    # DEFAULT ARVIND ACCOUNT
    # -----------------------------------------------------

    username = "arvind"
    password = "Jugnu@123"

    password_hash = hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()

    cur.execute(
        "SELECT username FROM users WHERE username=?",
        (username,)
    )

    if cur.fetchone() is None:

        cur.execute(
            """
            INSERT INTO users
            (username, name, plan, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                "अरविंद सिंह",
                "VIP PRO",
                datetime.now().isoformat()
            )
        )

    cur.execute(
        "SELECT username FROM auth_users WHERE username=?",
        (username,)
    )

    if cur.fetchone() is None:

        cur.execute(
            """
            INSERT INTO auth_users
            (username, password_hash)
            VALUES (?, ?)
            """,
            (
                username,
                password_hash
            )
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
            return str(value)

    except Exception:
        pass

    return os.getenv(name, "")


GROQ_API_KEY = get_secret("GROQ_API_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

COOKIE_PASSWORD = get_secret("COOKIE_PASSWORD")

if not COOKIE_PASSWORD:
    COOKIE_PASSWORD = "JugnuAI_Default_Cookie_Secret_2026"


# =========================================================
# COOKIE MANAGER
# =========================================================

cookies = None

if COOKIE_AVAILABLE:

    try:

        cookies = EncryptedCookieManager(
            prefix="jugnu-ai/",
            password=COOKIE_PASSWORD
        )

        if not cookies.ready():
            st.stop()

    except Exception:
        cookies = None


def save_login_cookie(username):

    if cookies is None:
        return

    try:
        cookies["logged_in_user"] = username
        cookies.save()
    except Exception:
        pass


def get_login_cookie():

    if cookies is None:
        return None

    try:

        username = cookies.get("logged_in_user")

        if username:
            return username

    except Exception:
        pass

    return None


def clear_login_cookie():

    if cookies is None:
        return

    try:

        if "logged_in_user" in cookies:
            del cookies["logged_in_user"]

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
        SELECT * FROM users
        WHERE username=?
        """,
        (username,)
    ).fetchone()

    conn.close()

    return row


def verify_login(username, password):

    conn = get_db()

    row = conn.execute(
        """
        SELECT password_hash
        FROM auth_users
        WHERE username=?
        """,
        (username,)
    ).fetchone()

    conn.close()

    if not row:
        return False

    return row["password_hash"] == hash_password(password)


def create_user(username, name, password):

    conn = get_db()

    try:

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
                datetime.now().isoformat()
            )
        )

        conn.execute(
            """
            INSERT INTO auth_users
            (username, password_hash)
            VALUES (?, ?)
            """,
            (
                username,
                hash_password(password)
            )
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


def change_password(username, new_password):

    conn = get_db()

    conn.execute(
        """
        UPDATE auth_users
        SET password_hash=?
        WHERE username=?
        """,
        (
            hash_password(new_password),
            username
        )
    )

    conn.commit()
    conn.close()


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
        (username,)
    ).fetchone()

    if row is None:

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
                "सामान्य"
            )
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM app_settings
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
# CONVERSATIONS
# =========================================================

def create_conversation(username, title="नई चैट"):

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO conversations
        (username, title, created_at)
        VALUES (?, ?, ?)
        """,
        (
            username,
            title,
            datetime.now().isoformat()
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
        SELECT *
        FROM conversations
        WHERE username=?
        ORDER BY id DESC
        """,
        (username,)
    ).fetchall()

    conn.close()

    return rows


def delete_conversation(conversation_id, username):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM messages
        WHERE conversation_id=?
        AND username=?
        """,
        (
            conversation_id,
            username
        )
    )

    conn.execute(
        """
        DELETE FROM conversations
        WHERE id=?
        AND username=?
        """,
        (
            conversation_id,
            username
        )
    )

    conn.commit()
    conn.close()


def save_message(
    username,
    conversation_id,
    role,
    content,
    image_data=None
):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO messages
        (username, conversation_id, role, content, image_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            conversation_id,
            role,
            content,
            image_data,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


def get_messages(username, conversation_id):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM messages
        WHERE username=?
        AND conversation_id=?
        ORDER BY id ASC
        """,
        (
            username,
            conversation_id
        )
    ).fetchall()

    conn.close()

    return rows


def update_conversation_title(
    username,
    conversation_id,
    title
):

    conn = get_db()

    conn.execute(
        """
        UPDATE conversations
        SET title=?
        WHERE username=?
        AND id=?
        """,
        (
            title[:60],
            username,
            conversation_id
        )
    )

    conn.commit()
    conn.close()


# =========================================================
# MEMORY
# =========================================================

def add_memory(username, memory):

    if not memory:
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
            memory[:1000],
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


def get_memories(username):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM user_memories
        WHERE username=?
        ORDER BY id DESC
        LIMIT 20
        """,
        (username,)
    ).fetchall()

    conn.close()

    return rows


def delete_all_memories(username):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM user_memories
        WHERE username=?
        """,
        (username,)
    )

    conn.commit()
    conn.close()


# =========================================================
# NOTES / REMINDERS
# =========================================================

def save_note(username, title, content):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO notes
        (username, title, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            title,
            content,
            datetime.now().isoformat()
        )
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
        (username,)
    ).fetchall()

    conn.close()

    return rows


# =========================================================
# GROQ CLIENT
# =========================================================

groq_client = None

if GROQ_API_KEY:

    try:

        groq_client = Groq(
            api_key=GROQ_API_KEY
        )

    except Exception:
        groq_client = None


# =========================================================
# GEMINI CLIENT
# =========================================================

def get_gemini_client():

    if not GEMINI_AVAILABLE:
        return None

    if not GEMINI_API_KEY:
        return None

    try:

        return genai.Client(
            api_key=GEMINI_API_KEY
        )

    except Exception:

        return None


# =========================================================
# GEMINI IMAGE GENERATION
# =========================================================

def generate_gemini_image(prompt):

    if not GEMINI_AVAILABLE:
        return None, "Gemini library उपलब्ध नहीं है।"

    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY नहीं मिली।"

    try:

        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        response = client.interactions.create(
            model=GEMINI_IMAGE_MODEL,
            input=prompt,
            response_format={
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": "1:1",
                "image_size": "1K"
            }
        )

        image_bytes = None

        if hasattr(response, "outputs"):

            for output in response.outputs:

                if hasattr(output, "image"):

                    image_obj = output.image

                    if hasattr(image_obj, "data"):

                        image_bytes = image_obj.data

                        if isinstance(image_bytes, str):

                            image_bytes = base64.b64decode(
                                image_bytes
                            )

                        break

        if image_bytes is None:

            try:

                for item in response:

                    if hasattr(item, "data"):

                        image_bytes = item.data
                        break

            except Exception:
                pass

        if image_bytes is None:

            return None, "Gemini ने image data वापस नहीं दिया।"

        return image_bytes, None

    except Exception as e:

        return None, str(e)


# =========================================================
# PHOTO REQUEST DETECTION
# =========================================================

def is_image_request(prompt):

    p = prompt.lower()

    keywords = [
        "image",
        "photo",
        "picture",
        "draw",
        "generate image",
        "create image",
        "make image",
        "तस्वीर",
        "फोटो",
        "चित्र",
        "इमेज",
        "बना दो",
        "बनाओ",
        "तस्वीर बनाओ",
        "फोटो बनाओ"
    ]

    return any(
        word in p
        for word in keywords
    )


def clean_image_prompt(prompt):

    replacements = [
        "image बनाओ",
        "image बना दो",
        "image generate करो",
        "photo बनाओ",
        "तस्वीर बनाओ",
        "फोटो बनाओ",
        "इमेज बनाओ"
    ]

    result = prompt

    for item in replacements:

        result = result.replace(
            item,
            "",
            1
        )

    return result.strip()


# =========================================================
# WEB SEARCH
# =========================================================

def web_search(query, max_results=5):

    if not DDGS_AVAILABLE:
        return []

    try:

        results = []

        with DDGS() as ddgs:

            for item in ddgs.text(
                query,
                max_results=max_results
            ):

                results.append(item)

        return results

    except Exception:

        return []


def format_web_results(results):

    if not results:
        return ""

    text = "\n\nWEB SEARCH RESULTS:\n"

    for i, result in enumerate(
        results,
        start=1
    ):

        title = result.get(
            "title",
            ""
        )

        body = result.get(
            "body",
            ""
        )

        href = result.get(
            "href",
            ""
        )

        text += (
            f"\n{i}. {title}\n"
            f"{body}\n"
            f"{href}\n"
        )

    return text


# =========================================================
# PDF / TXT
# =========================================================

def extract_pdf_text(file):

    try:

        reader = PdfReader(file)

        pages = []

        for page in reader.pages:

            try:
                pages.append(
                    page.extract_text() or ""
                )
            except Exception:
                pass

        return "\n".join(pages)

    except Exception as e:

        return f"PDF पढ़ने में समस्या: {e}"


def extract_txt_text(file):

    try:

        data = file.read()

        try:
            return data.decode("utf-8")
        except Exception:
            return data.decode(
                "latin-1",
                errors="ignore"
            )

    except Exception as e:

        return f"TXT पढ़ने में समस्या: {e}"


# =========================================================
# VOICE TRANSCRIPTION
# =========================================================

def transcribe_audio(audio_file):

    if groq_client is None:
        return None

    try:

        audio_bytes = audio_file.read()

        temp_name = "jugnu_voice_input.wav"

        with open(
            temp_name,
            "wb"
        ) as f:

            f.write(audio_bytes)

        with open(
            temp_name,
            "rb"
        ) as f:

            transcription = groq_client.audio.transcriptions.create(
                file=f,
                model=WHISPER_MODEL
            )

        try:
            os.remove(temp_name)
        except Exception:
            pass

        return transcription.text

    except Exception:

        return None


# =========================================================
# TEXT TO SPEECH
# =========================================================

def get_tts_language(language):

    if language == "English":
        return "en"

    return "hi"


def make_tts(
    text,
    language="Hindi",
    voice_speed="सामान्य"
):

    if not text:
        return None

    try:

        lang = get_tts_language(
            language
        )

        slow = (
            voice_speed == "धीमी"
        )

        tts = gTTS(
            text=text,
            lang=lang,
            slow=slow
        )

        audio = io.BytesIO()

        tts.write_to_fp(audio)

        audio.seek(0)

        return audio.getvalue()

    except Exception:

        return None


# =========================================================
# CREATOR INFORMATION
# =========================================================

def creator_answer():

    return (
        "मुझे अरविंद सिंह ने बनाया है। "
        "मेरे निर्माता अरविंद सिंह हैं। "
        "मेरे निर्माता के पिता का नाम Mr Rewant Singh है। "
        "उनका गाँव Doojasar है और वे वर्तमान में "
        "Shri Mohangarh में हैं।"
    )


def is_creator_question(prompt):

    p = prompt.lower().strip()

    creator_phrases = [

        # English
        "creator",
        "who is your creator",
        "who created you",
        "who made you",
        "who built you",
        "who developed you",
        "who is your maker",
        "your maker",
        "your creator",
        "maker",
        "owner",

        # Hindi / Hinglish
        "creator कौन",
        "creator कौन है",
        "creator kaun",
        "creator kaun hai",

        "maker कौन",
        "maker कौन है",
        "maker kaun",
        "maker kaun hai",

        "owner कौन",
        "owner कौन है",
        "owner kaun",
        "owner kaun hai",

        "तुम्हारा creator कौन है",
        "तुम्हारा क्रिएटर कौन है",
        "तुम्हारा क्रिएटर कौन है",

        "तुमको किसने बनाया",
        "तुमको किसने बनाया है",
        "तुमको किसने बनाया था",

        "तुम्हें किसने बनाया",
        "तुम्हें किसने बनाया है",
        "तुम्हें किसने बनाया था",

        "तुमको किसने बनाया है",

        "जुगनू को किसने बनाया",
        "जुगनू को किसने बनाया है",
        "जुगनू किसने बनाई",
        "जुगनू किसने बनाया",
        "जुगनू किसने बनाया है",

        "जुगनू का निर्माता कौन है",
        "जुगनू के निर्माता कौन हैं",

        "तुम्हारा निर्माता कौन है",
        "तुम्हारे निर्माता कौन हैं",
        "तुम्हारे निर्माता कौन है",

        "तुम्हारा मालिक कौन है",
        "तुम्हारा मालिक कौन है",

        "बनाने वाला कौन है",
        "बनाने वाला कौन है तुम्हारा",
        "बनाने वाले का नाम",

        "निर्माता कौन है",
        "निर्माता का नाम",

        "किसने बनाया है तुम्हें",
        "किसने बनाया तुम्हें",

        "अरविंद सिंह ने बनाया",
        "अरविंद सिंह ने तुम्हें बनाया",
        "अरविंद सिंह कौन है"
    ]

    return any(
        phrase in p
        for phrase in creator_phrases
    )


# =========================================================
# SYSTEM PROMPT
# =========================================================

def build_system_prompt(
    language,
    bot_mode,
    memories=None
):

    if bot_mode == "दोस्ताना":

        personality = """
तुम जुगनू AI हो।
तुम बहुत friendly, सरल और मददगार तरीके से बात करती हो।
"""

    elif bot_mode == "शिक्षक":

        personality = """
तुम जुगनू AI हो।
तुम एक अच्छे शिक्षक की तरह सरल भाषा में समझाती हो।
जरूरत हो तो उदाहरण और step-by-step तरीका देती हो।
"""

    elif bot_mode == "कहानीकार":

        personality = """
तुम जुगनू AI हो।
तुम कहानीकार की तरह रोचक, भावनात्मक और कल्पनाशील अंदाज में जवाब देती हो।
"""

    elif bot_mode == "मारवाड़ी / राजस्थानी":

        personality = """
तुम जुगनू AI हो।
जरूरत पड़ने पर मारवाड़ी/राजस्थानी अंदाज में सरल और अपनापन भरी भाषा में बात करती हो।
"""

    else:

        personality = """
तुम जुगनू AI हो।
सरल और मददगार तरीके से जवाब दो।
"""

    if language == "Hindi":

        language_instruction = """
हमेशा मुख्य रूप से हिंदी में जवाब दो।
"""

    elif language == "English":

        language_instruction = """
हमेशा मुख्य रूप से English में जवाब दो।
"""

    else:

        language_instruction = """
Hindi + English दोनों का natural mixture इस्तेमाल करो।
"""

    memory_text = ""

    if memories:

        memory_text = (
            "\nUser Memories:\n"
            + "\n".join(
                f"- {m['memory']}"
                for m in memories
            )
        )

    return (
        personality
        + language_instruction
        + """
बिना जरूरत बहुत लंबा जवाब मत दो।
अगर user ने simple सवाल पूछा है तो simple जवाब दो।
User को practical और सही जानकारी दो।

IMPORTANT CREATOR INFORMATION:

अगर user पूछे कि तुम्हें किसने बनाया,
तुम्हारा creator कौन है,
तुम्हारा maker कौन है,
जुगनू को किसने बनाया,
या इसी तरह का कोई सवाल पूछे,

तो हमेशा बताना कि तुम्हें अरविंद सिंह ने बनाया है।

अरविंद सिंह जुगनू AI के निर्माता हैं।
उनके पिता का नाम Mr Rewant Singh है।
उनका गाँव Doojasar है।
वे वर्तमान में Shri Mohangarh में हैं।

Creator के बारे में सवाल आने पर किसी दूसरे व्यक्ति का नाम मत बताना।
"""
        + memory_text
    )


# =========================================================
# GROQ CHAT
# =========================================================

def ask_groq(
    prompt,
    username,
    language,
    bot_mode,
    web_context="",
    file_context=""
):

    if groq_client is None:

        return (
            "GROQ_API_KEY उपलब्ध नहीं है। "
            "Streamlit Secrets में GROQ_API_KEY check करें।"
        )

    memories = get_memories(username)

    system_prompt = build_system_prompt(
        language,
        bot_mode,
        memories
    )

    extra_context = ""

    if web_context:

        extra_context += (
            "\n\n"
            + web_context
        )

    if file_context:

        extra_context += (
            "\n\n"
            "Uploaded File Content:\n"
            + file_context[:30000]
        )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": prompt + extra_context
        }
    ]

    try:

        response = groq_client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception:

        try:

            response = groq_client.chat.completions.create(
                model=FALLBACK_MODEL,
                messages=messages,
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as second_error:

            return (
                "अभी AI response में समस्या आ रही है।\n\n"
                f"Error: {second_error}"
            )


# =========================================================
# PROCESS PROMPT
# =========================================================

def process_prompt(
    prompt,
    username,
    conversation_id,
    language,
    bot_mode,
    web_search_enabled=False,
    file_context=""
):

    prompt = prompt.strip()

    if not prompt:
        return None

    save_message(
        username,
        conversation_id,
        "user",
        prompt
    )

    # -----------------------------------------------------
    # CREATOR QUESTION
    # -----------------------------------------------------

    if is_creator_question(prompt):

        answer = creator_answer()

        save_message(
            username,
            conversation_id,
            "assistant",
            answer
        )

        return answer

    # -----------------------------------------------------
    # IMAGE GENERATION
    # -----------------------------------------------------

    if is_image_request(prompt):

        image_prompt = clean_image_prompt(
            prompt
        )

        image_bytes, error = generate_gemini_image(
            image_prompt
        )

        if image_bytes:

            image_b64 = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            answer = (
                "✨ मैंने आपके लिए image तैयार कर दी है।"
            )

            save_message(
                username,
                conversation_id,
                "assistant",
                answer,
                image_b64
            )

            return {
                "text": answer,
                "image": image_bytes
            }

        else:

            answer = (
                "Image बनाने में समस्या आई:\n\n"
                + str(error)
            )

            save_message(
                username,
                conversation_id,
                "assistant",
                answer
            )

            return answer

    # -----------------------------------------------------
    # WEB SEARCH
    # -----------------------------------------------------

    web_context = ""

    if web_search_enabled:

        search_words = [
            "latest",
            "today",
            "news",
            "current",
            "price",
            "weather",
            "आज",
            "अभी",
            "ताजा",
            "लेटेस्ट",
            "न्यूज़",
            "कीमत"
        ]

        if any(
            x in prompt.lower()
            for x in search_words
        ):

            results = web_search(
                prompt
            )

            web_context = format_web_results(
                results
            )

    # -----------------------------------------------------
    # MEMORY REQUEST
    # -----------------------------------------------------

    memory_match = re.search(
        r"(याद रखना|याद रखो|remember that|remember)",
        prompt,
        re.IGNORECASE
    )

    if memory_match:

        memory = re.sub(
            r"(याद रखना|याद रखो|remember that|remember)",
            "",
            prompt,
            flags=re.IGNORECASE
        ).strip()

        if memory:

            add_memory(
                username,
                memory
            )

            answer = (
                "ठीक है 😊 मैंने इसे याद रखने के लिए save कर लिया।"
            )

            save_message(
                username,
                conversation_id,
                "assistant",
                answer
            )

            return answer

    # -----------------------------------------------------
    # NORMAL AI
    # -----------------------------------------------------

    answer = ask_groq(
        prompt,
        username,
        language,
        bot_mode,
        web_context,
        file_context
    )

    save_message(
        username,
        conversation_id,
        "assistant",
        answer
    )

    return answer


# =========================================================
# AUDIO HELPER
# =========================================================

def prepare_voice_response(
    response,
    language,
    voice_speed
):

    if not response:
        return None

    if isinstance(response, dict):

        text = response.get(
            "text",
            ""
        )

    else:

        text = str(response)

    if not text:
        return None

    return make_tts(
        text,
        language,
        voice_speed
    )


# =========================================================
# SESSION STATE
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = None

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if "pending_audio" not in st.session_state:
    st.session_state.pending_audio = None

if "pending_response" not in st.session_state:
    st.session_state.pending_response = None

if "file_context" not in st.session_state:
    st.session_state.file_context = ""


# =========================================================
# RESTORE LOGIN FROM COOKIE
# =========================================================

if not st.session_state.logged_in:

    saved_username = get_login_cookie()

    if saved_username:

        user = get_user(
            saved_username
        )

        if user:

            st.session_state.logged_in = True
            st.session_state.username = saved_username


# =========================================================
# LOGIN / SIGNUP PAGE
# =========================================================

if not st.session_state.logged_in:

    st.markdown(
        '<div class="jugnu-title">✨ जुगनू AI</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="jugnu-subtitle">आपका अपना AI साथी</div>',
        unsafe_allow_html=True
    )

    login_tab, signup_tab, guest_tab = st.tabs(
        [
            "🔐 Login",
            "📝 Sign Up",
            "👤 Guest"
        ]
    )

    with login_tab:

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
            "🔐 Login",
            use_container_width=True
        ):

            if verify_login(
                username,
                password
            ):

                st.session_state.logged_in = True
                st.session_state.username = username

                save_login_cookie(
                    username
                )

                st.rerun()

            else:

                st.error(
                    "Username या Password गलत है।"
                )

    with signup_tab:

        new_name = st.text_input(
            "आपका नाम"
        )

        new_username = st.text_input(
            "नया Username"
        )

        new_password = st.text_input(
            "नया Password",
            type="password"
        )

        confirm_password = st.text_input(
            "Password फिर से डालें",
            type="password"
        )

        if st.button(
            "📝 Account बनाएं",
            use_container_width=True
        ):

            if not new_name or not new_username or not new_password:

                st.warning(
                    "सभी जानकारी भरें।"
                )

            elif new_password != confirm_password:

                st.error(
                    "दोनों Password समान नहीं हैं।"
                )

            else:

                success = create_user(
                    new_username,
                    new_name,
                    new_password
                )

                if success:

                    st.success(
                        "Account बन गया। अब Login करें।"
                    )

                else:

                    st.error(
                        "यह Username पहले से मौजूद है।"
                    )

    with guest_tab:

        st.write(
            "बिना account के जुगनू AI इस्तेमाल करें।"
        )

        if st.button(
            "👤 Guest के रूप में जारी रखें",
            use_container_width=True
        ):

            guest_username = (
                "guest_"
                + datetime.now().strftime(
                    "%Y%m%d%H%M%S"
                )
            )

            create_user(
                guest_username,
                "Guest User",
                hashlib.sha256(
                    os.urandom(16)
                ).hexdigest()
            )

            st.session_state.logged_in = True
            st.session_state.username = guest_username

            st.rerun()

    st.stop()


# =========================================================
# USER
# =========================================================

username = st.session_state.username

user = get_user(username)

if user is None:

    st.session_state.logged_in = False
    clear_login_cookie()
    st.rerun()


user_name = user["name"]
user_plan = user["plan"]


# =========================================================
# SETTINGS LOAD
# =========================================================

settings = get_settings(
    username
)

language = settings["language"]
bot_mode = settings["bot_mode"]
voice_speed = settings["voice_speed"]


# =========================================================
# CREATE CHAT IF NONE
# =========================================================

if st.session_state.conversation_id is None:

    st.session_state.conversation_id = create_conversation(
        username,
        "नई चैट"
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        "## ✨ जुगनू AI"
    )

    st.write(
        f"👋 नमस्ते **{user_name}**"
    )

    st.caption(
        f"Plan: {user_plan}"
    )

    st.divider()

    if st.button(
        "➕ नई चैट",
        use_container_width=True
    ):

        st.session_state.conversation_id = create_conversation(
            username,
            "नई चैट"
        )

        st.session_state.pending_audio = None

        st.rerun()

    web_search_enabled = st.toggle(
        "🌐 Web Search",
        value=False
    )

    voice_response = st.toggle(
        "🔊 Voice Response",
        value=True
    )

    st.divider()

    with st.expander(
        "⚙️ Settings",
        expanded=False
    ):

        st.markdown(
            "### 🌐 Language"
        )

        new_language = st.selectbox(
            "Language",
            [
                "Hindi",
                "English",
                "Hindi + English"
            ],
            index=[
                "Hindi",
                "English",
                "Hindi + English"
            ].index(language),
            key="settings_language"
        )

        st.markdown(
            "### 🤖 जुगनू का अंदाज"
        )

        new_bot_mode = st.selectbox(
            "Bot Mode",
            [
                "दोस्ताना",
                "शिक्षक",
                "कहानीकार",
                "मारवाड़ी / राजस्थानी"
            ],
            index=[
                "दोस्ताना",
                "शिक्षक",
                "कहानीकार",
                "मारवाड़ी / राजस्थानी"
            ].index(bot_mode),
            key="settings_bot_mode"
        )

        st.markdown(
            "### 🔊 Voice Speed"
        )

        new_voice_speed = st.selectbox(
            "आवाज की गति",
            [
                "सामान्य",
                "धीमी"
            ],
            index=[
                "सामान्य",
                "धीमी"
            ].index(voice_speed),
            key="settings_voice_speed"
        )

        if st.button(
            "💾 Settings Save",
            use_container_width=True
        ):

            save_settings(
                username,
                new_language,
                new_bot_mode,
                new_voice_speed
            )

            st.success(
                "Settings save हो गईं।"
            )

            st.rerun()

        st.divider()

        st.markdown(
            "### 🔑 Password बदलें"
        )

        old_password = st.text_input(
            "पुराना Password",
            type="password",
            key="old_password"
        )

        new_password = st.text_input(
            "नया Password",
            type="password",
            key="new_password"
        )

        confirm_new_password = st.text_input(
            "नया Password फिर से",
            type="password",
            key="confirm_new_password"
        )

        if st.button(
            "🔐 Password Update",
            use_container_width=True
        ):

            if not verify_login(
                username,
                old_password
            ):

                st.error(
                    "पुराना Password गलत है।"
                )

            elif new_password != confirm_new_password:

                st.error(
                    "नया Password समान नहीं है।"
                )

            elif not new_password:

                st.error(
                    "नया Password डालें।"
                )

            else:

                change_password(
                    username,
                    new_password
                )

                st.success(
                    "Password बदल गया।"
                )

        st.divider()

        if st.button(
            "🗑️ Current Chat Delete",
            use_container_width=True
        ):

            delete_conversation(
                st.session_state.conversation_id,
                username
            )

            st.session_state.conversation_id = create_conversation(
                username,
                "नई चैट"
            )

            st.session_state.pending_audio = None

            st.rerun()

    with st.expander(
        "🧠 Memory"
    ):

        memories = get_memories(
            username
        )

        if memories:

            for memory in memories:

                st.write(
                    "• " + memory["memory"]
                )

        else:

            st.caption(
                "अभी कोई Memory नहीं है।"
            )

        if st.button(
            "🗑️ सभी Memory Delete करें",
            use_container_width=True
        ):

            delete_all_memories(
                username
            )

            st.rerun()

    with st.expander(
        "📝 Reminders / Diary"
    ):

        note_title = st.text_input(
            "Title",
            key="note_title"
        )

        note_content = st.text_area(
            "Reminder / Note",
            key="note_content"
        )

        if st.button(
            "💾 Save Note",
            use_container_width=True
        ):

            if note_content:

                save_note(
                    username,
                    note_title or "Note",
                    note_content
                )

                st.success(
                    "Note save हो गई।"
                )

        notes = get_notes(
            username
        )

        if notes:

            st.markdown(
                "### Saved Notes"
            )

            for note in notes[:10]:

                st.write(
                    f"**{note['title']}**"
                )

                st.caption(
                    note["content"]
                )

    with st.expander(
        "💬 Chat History"
    ):

        conversations = get_conversations(
            username
        )

        for conv in conversations[:20]:

            label = (
                conv["title"]
                if conv["title"]
                else "नई चैट"
            )

            if st.button(
                "💬 " + label,
                key=f"chat_{conv['id']}",
                use_container_width=True
            ):

                st.session_state.conversation_id = conv["id"]
                st.session_state.pending_audio = None

                st.rerun()

    with st.expander(
        "👑 VIP Dashboard"
    ):

        st.write(
            f"User: **{user_name}**"
        )

        st.write(
            f"Plan: **{user_plan}**"
        )

        st.write("✨ AI Chat")
        st.write("🖼️ AI Image Generation")
        st.write("🧠 Memory")
        st.write("🌐 Web Search")
        st.write("🎤 Voice")

    with st.expander(
        "👨‍💻 निर्माता"
    ):

        st.markdown(
            """
            <div class="creator-box">
            <b>नाम:</b> अरविंद सिंह<br><br>
            <b>पिता:</b> Mr Rewant Singh<br><br>
            <b>गाँव:</b> Doojasar<br><br>
            <b>वर्तमान:</b> Shri Mohangarh
            </div>
            """,
            unsafe_allow_html=True
        )

    st.divider()

    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        clear_login_cookie()

        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.conversation_id = None
        st.session_state.pending_audio = None

        st.rerun()


# =========================================================
# MAIN HEADER
# =========================================================

st.markdown(
    '<div class="jugnu-title">✨ जुगनू AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="jugnu-subtitle">आपका अपना AI साथी</div>',
    unsafe_allow_html=True
)


# =========================================================
# QUICK ACTIONS
# =========================================================

st.markdown(
    "### ⚡ Quick Actions"
)

q1, q2, q3, q4 = st.columns(4)

quick_prompt = None

with q1:

    if st.button(
        "📚 पढ़ाई में मदद",
        use_container_width=True
    ):

        quick_prompt = (
            "मुझे पढ़ाई की एक अच्छी strategy बताओ।"
        )

with q2:

    if st.button(
        "💡 आज कुछ सिखाओ",
        use_container_width=True
    ):

        quick_prompt = (
            "आज मुझे कोई useful और interesting चीज सिखाओ।"
        )

with q3:

    if st.button(
        "😂 कुछ मजेदार",
        use_container_width=True
    ):

        quick_prompt = (
            "मुझे कुछ मजेदार सुनाओ।"
        )

with q4:

    if st.button(
        "📖 कहानी सुनाओ",
        use_container_width=True
    ):

        quick_prompt = (
            "मुझे एक छोटी और interesting कहानी सुनाओ।"
        )


# =========================================================
# PDF / TXT UPLOAD
# =========================================================

with st.expander(
    "📄 PDF / TXT पढ़ाएँ"
):

    uploaded_file = st.file_uploader(
        "PDF या TXT file चुनें",
        type=[
            "pdf",
            "txt"
        ]
    )

    if uploaded_file:

        if uploaded_file.type == "application/pdf":

            text = extract_pdf_text(
                uploaded_file
            )

        else:

            text = extract_txt_text(
                uploaded_file
            )

        st.session_state.file_context = text

        st.success(
            "File पढ़ ली गई है। अब इसके बारे में सवाल पूछ सकते हैं।"
        )

        st.text_area(
            "File Preview",
            text[:5000],
            height=180
        )


# =========================================================
# IMAGE UPLOAD
# =========================================================

with st.expander(
    "📷 Image Upload"
):

    uploaded_image = st.file_uploader(
        "Image चुनें",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp"
        ],
        key="image_upload"
    )

    if uploaded_image:

        try:

            image = Image.open(
                uploaded_image
            )

            st.image(
                image,
                caption="Uploaded Image",
                use_container_width=True
            )

            st.info(
                "Image upload हो गई है।"
            )

        except Exception:

            st.error(
                "Image पढ़ने में समस्या आई।"
            )


# =========================================================
# VOICE INPUT
# =========================================================

with st.expander(
    "🎤 Voice Input"
):

    audio_file = st.file_uploader(
        "अपनी आवाज upload करें",
        type=[
            "wav",
            "mp3",
            "m4a",
            "ogg",
            "webm"
        ],
        key="voice_upload"
    )

    if audio_file:

        if st.button(
            "🎤 Voice को Text में बदलें",
            use_container_width=True
        ):

            voice_text = transcribe_audio(
                audio_file
            )

            if voice_text:

                st.session_state.voice_prompt = voice_text

                st.success(
                    "Voice समझ ली गई:"
                )

                st.write(
                    voice_text
                )

            else:

                st.error(
                    "Voice समझने में समस्या आई।"
                )


# =========================================================
# CHAT HISTORY DISPLAY
# =========================================================

messages = get_messages(
    username,
    st.session_state.conversation_id
)


for msg in messages:

    role = msg["role"]
    content = msg["content"]
    image_data = msg["image_data"]

    if role == "user":

        st.markdown(
            f"""
            <div class="chat-user">
            <b>👤 आप</b><br>
            {content}
            </div>
            """,
            unsafe_allow_html=True
        )

    else:

        st.markdown(
            f"""
            <div class="chat-ai">
            <b>✨ जुगनू AI</b><br>
            {content}
            </div>
            """,
            unsafe_allow_html=True
        )

        if image_data:

            try:

                image_bytes = base64.b64decode(
                    image_data
                )

                st.image(
                    image_bytes,
                    caption="✨ Generated Image",
                    use_container_width=True
                )

                st.download_button(
                    "⬇️ Image Download",
                    data=image_bytes,
                    file_name="jugnu_generated_image.jpg",
                    mime="image/jpeg",
                    key=f"download_{msg['id']}"
                )

            except Exception:

                pass


# =========================================================
# SHOW PENDING AUDIO
# =========================================================

if st.session_state.pending_audio:

    st.markdown(
        "🔊 **जुगनू बोल रही है...**"
    )

    st.audio(
        st.session_state.pending_audio,
        format="audio/mp3"
    )

    st.session_state.pending_audio = None


# =========================================================
# PROCESS FUNCTION FOR ALL INPUTS
# =========================================================

def run_user_prompt(prompt):

    if not prompt:
        return

    response = process_prompt(
        prompt=prompt,
        username=username,
        conversation_id=st.session_state.conversation_id,
        language=language,
        bot_mode=bot_mode,
        web_search_enabled=web_search_enabled,
        file_context=st.session_state.file_context
    )

    current_messages = get_messages(
        username,
        st.session_state.conversation_id
    )

    user_messages = [
        x for x in current_messages
        if x["role"] == "user"
    ]

    if len(user_messages) == 1:

        title = prompt[:50]

        update_conversation_title(
            username,
            st.session_state.conversation_id,
            title
        )

    if voice_response:

        audio = prepare_voice_response(
            response,
            language,
            voice_speed
        )

        if audio:

            st.session_state.pending_audio = audio

    st.rerun()


# =========================================================
# QUICK ACTION EXECUTION
# =========================================================

if quick_prompt:

    run_user_prompt(
        quick_prompt
    )


# =========================================================
# VOICE PROMPT EXECUTION
# =========================================================

if st.session_state.get(
    "voice_prompt"
):

    voice_prompt = st.session_state.voice_prompt

    st.session_state.voice_prompt = None

    run_user_prompt(
        voice_prompt
    )


# =========================================================
# CHAT INPUT
# =========================================================

prompt = st.chat_input(
    "जुगनू से कुछ पूछिए..."
)

if prompt:

    run_user_prompt(
        prompt
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown(
    """
    <div style="
        text-align:center;
        color:#888;
        padding:30px;
        font-size:13px;
    ">
    ✨ जुगनू AI • आपका अपना AI साथी
    </div>
    """,
    unsafe_allow_html=True
)
