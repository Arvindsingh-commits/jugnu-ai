import os
import io
import re
import sqlite3
import hashlib
from datetime import datetime
from urllib.parse import quote

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
    initial_sidebar_state="expanded"
)


DB_FILE = "jugnu_data.db"

DEFAULT_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"
WHISPER_MODEL = "whisper-large-v3-turbo"

DEFAULT_USERNAME = "arvind"
DEFAULT_NAME = "अरविंद सिंह"


def get_secret(name):
    value = os.environ.get(name)
    if value:
        return value

    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass

    return None


GROQ_API_KEY = get_secret("GROQ_API_KEY")


@st.cache_resource
def get_groq_client(api_key):
    if not api_key:
        return None
    return Groq(api_key=api_key)


client = get_groq_client(GROQ_API_KEY)


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
            username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            plan TEXT DEFAULT 'FREE',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT DEFAULT 'नई चैट',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            task TEXT NOT NULL,
            reminder_time TEXT,
            created_at TEXT NOT NULL,
            completed INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            memory TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        INSERT OR IGNORE INTO users
        (username, name, plan, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            DEFAULT_USERNAME,
            DEFAULT_NAME,
            "VIP PRO",
            datetime.now().isoformat(timespec="seconds")
        )
    )

    conn.commit()
    conn.close()


init_db()


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_user(username):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()
    return row


def get_all_users():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM users ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return rows


def update_user_plan(username, plan):
    conn = get_db()
    conn.execute(
        "UPDATE users SET plan = ? WHERE username = ?",
        (plan, username)
    )
    conn.commit()
    conn.close()


def create_user(username, name, plan="FREE"):
    username = username.strip().lower()
    name = name.strip()

    if not username or not name:
        return False

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
                plan,
                now_text()
            )
        )
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False

    conn.close()
    return result


def create_conversation(username, title="नई चैट"):
    conn = get_db()

    cur = conn.execute(
        """
        INSERT INTO conversations
        (username, title, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            title[:100],
            now_text(),
            now_text()
        )
    )

    conversation_id = cur.lastrowid
    conn.commit()
    conn.close()

    return conversation_id


def update_conversation_title(conversation_id, title):
    conn = get_db()
    conn.execute(
        """
        UPDATE conversations
        SET title = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            title[:100],
            now_text(),
            conversation_id
        )
    )
    conn.commit()
    conn.close()


def add_message(conversation_id, role, content):
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
            now_text()
        )
    )

    conn.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE id = ?
        """,
        (now_text(), conversation_id)
    )

    conn.commit()
    conn.close()


def get_conversations(username, search_text=""):
    conn = get_db()

    if search_text.strip():
        rows = conn.execute(
            """
            SELECT *
            FROM conversations
            WHERE username = ?
            AND title LIKE ?
            ORDER BY updated_at DESC
            """,
            (
                username,
                "%" + search_text.strip() + "%"
            )
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM conversations
            WHERE username = ?
            ORDER BY updated_at DESC
            """,
            (username,)
        ).fetchall()

    conn.close()
    return rows


def get_messages(conversation_id):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,)
    ).fetchall()

    conn.close()
    return rows


def add_memory(username, memory):
    memory = memory.strip()

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
            memory,
            now_text()
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
        WHERE username = ?
        ORDER BY id DESC
        """,
        (username,)
    ).fetchall()

    conn.close()
    return rows


def clear_memories(username):
    conn = get_db()

    conn.execute(
        """
        DELETE FROM user_memories
        WHERE username = ?
        """,
        (username,)
    )

    conn.commit()
    conn.close()


def add_note(username, task, reminder_time):
    task = task.strip()

    if not task:
        return

    conn = get_db()

    conn.execute(
        """
        INSERT INTO notes
        (username, task, reminder_time, created_at, completed)
        VALUES (?, ?, ?, ?, 0)
        """,
        (
            username,
            task,
            reminder_time,
            now_text()
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
        WHERE username = ?
        ORDER BY completed ASC, id DESC
        """,
        (username,)
    ).fetchall()

    conn.close()
    return rows


def complete_note(note_id):
    conn = get_db()

    conn.execute(
        """
        UPDATE notes
        SET completed = 1
        WHERE id = ?
        """,
        (note_id,)
    )

    conn.commit()
    conn.close()


def delete_note(note_id):
    conn = get_db()

    conn.execute(
        """
        DELETE FROM notes
        WHERE id = ?
        """,
        (note_id,)
    )

    conn.commit()
    conn.close()


def clean_text(text):
    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = text.replace("\u2007", " ")
    text = text.replace("\u202f", " ")

    return text


def normalize_user_text(text):
    text = clean_text(text)
    return text.strip()


def is_marwari_request(text):
    t = text.lower()

    keywords = [
        "मारवाड़ी",
        "मारवाड़ी",
        "राजस्थानी",
        "marwari",
        "rajasthani"
    ]

    return any(word in t for word in keywords)


def is_creator_question(text):
    t = text.lower()

    keywords = [
        "creator",
        "creator कौन",
        "बनाने वाला",
        "किसने बनाया",
        "तुम्हारा मालिक",
        "तुम्हें किसने बनाया",
        "अरविंद सिंह",
        "arvind singh"
    ]

    return any(word in t for word in keywords)


def is_photo_request(text):
    t = text.lower()

    keywords = [
        "फोटो बनाओ",
        "फोटो बना",
        "image बनाओ",
        "image बना",
        "photo बनाओ",
        "photo बना",
        "generate image",
        "generate photo",
        "चित्र बनाओ",
        "तस्वीर बनाओ"
    ]

    return any(word in t for word in keywords)


def get_photo_url(prompt):
    safe_prompt = quote(
        normalize_user_text(prompt),
        safe=""
    )

    return (
        "https://image.pollinations.ai/prompt/"
        + safe_prompt
        + "?width=1024&height=1024&nologo=true"
    )


def live_search(query, max_results=5):
    if DDGS is None:
        return ""

    try:
        results = []

        with DDGS() as ddgs:
            search_results = ddgs.text(
                query,
                max_results=max_results
            )

            for item in search_results:
                title = item.get("title", "")
                body = item.get("body", "")
                href = item.get("href", "")

                results.append(
                    f"शीर्षक: {title}\n"
                    f"जानकारी: {body}\n"
                    f"लिंक: {href}"
                )

        return "\n\n".join(results)

    except Exception as e:
        return f"Live search unavailable: {str(e)}"


def should_search_web(text):
    t = text.lower()

    keywords = [
        "आज",
        "अभी",
        "लेटेस्ट",
        "latest",
        "news",
        "समाचार",
        "मौसम",
        "weather",
        "price",
        "कीमत",
        "भाव",
        "रेट",
        "rate",
        "आज का",
        "current",
        "live",
        "ताजा",
        "नया"
    ]

    return any(word in t for word in keywords)


def get_system_prompt(user, memories, mode, language):
    memory_text = ""

    if memories:
        memory_text = "\n".join(
            f"- {row['memory']}"
            for row in memories
        )

    if not memory_text:
        memory_text = "अभी कोई saved memory नहीं है।"

    language_instruction = (
        "यूजर हिंदी में बात करे तो सरल हिंदी में जवाब दो। "
        "यूजर English में बात करे तो English में जवाब दो।"
    )

    mode_instruction = ""

    if mode == "मारवाड़ी / राजस्थानी":
        mode_instruction = (
            "यूजर मारवाड़ी या राजस्थानी मांगे तो सरल, प्यारी और "
            "स्वाभाविक मारवाड़ी/राजस्थानी में जवाब दे।"
        )

    elif mode == "दोस्ताना":
        mode_instruction = (
            "दोस्त की तरह natural और friendly तरीके से बात करो।"
        )

    elif mode == "शिक्षक":
        mode_instruction = (
            "शिक्षक की तरह साफ, step-by-step और आसान तरीके से समझाओ।"
        )

    elif mode == "कहानीकार":
        mode_instruction = (
            "कहानीकार की तरह रोचक लेकिन स्पष्ट भाषा का प्रयोग करो।"
        )

    return f"""
तुम "जुगनू AI" हो।

तुम अरविंद सिंह के personal smart companion हो।

तुम्हारा creator:
अरविंद सिंह
गाँव दूजासर
श्री मोहनगढ़

तुम्हारा व्यवहार:
- मददगार
- ईमानदार
- सीधा
- natural
- सरल
- जरूरत पड़ने पर detail में
- बिना जरूरत बहुत लंबा जवाब नहीं
- गलत जानकारी को तथ्य की तरह मत बताओ
- अगर live information उपलब्ध नहीं है तो साफ बताओ

{language_instruction}

{mode_instruction}

यूजर की saved memories:
{memory_text}

यूजर का plan:
{user['plan']}

अगर यूजर स्वास्थ्य, कानूनी, वित्तीय या अन्य महत्वपूर्ण विषय पूछता है,
तो सावधानी से जवाब दो और जरूरत होने पर professional advice लेने को कहो।

अगर web search का context दिया गया है,
तो उसे उपयोग करके जवाब दो लेकिन search result को blindly copy मत करो।
"""


def extract_pdf_text(uploaded_file):
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)

        pages = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            pages.append(page_text)

        return "\n\n".join(pages)

    except Exception as e:
        return f"PDF पढ़ने में समस्या आई: {str(e)}"


def extract_txt_text(uploaded_file):
    try:
        data = uploaded_file.getvalue()

        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("utf-16")

    except Exception as e:
        return f"TXT पढ़ने में समस्या आई: {str(e)}"


def transcribe_audio(audio_file):
    if client is None:
        return "GROQ_API_KEY नहीं मिली।"

    try:
        audio_bytes = audio_file.getvalue()

        transcription = client.audio.transcriptions.create(
            file=(
                "audio.wav",
                audio_bytes,
                "audio/wav"
            ),
            model=WHISPER_MODEL,
            response_format="text"
        )

        if hasattr(transcription, "text"):
            return transcription.text

        return str(transcription)

    except Exception as e:
        return f"Voice transcription error: {str(e)}"


def generate_tts(text, language, speed):
    try:
        clean_for_voice = re.sub(
            r"https?://\S+",
            "",
            text
        )

        clean_for_voice = clean_for_voice.strip()

        if not clean_for_voice:
            return None

        lang = "hi" if language == "हिंदी" else "en"

        slow = speed == "धीमी"

        tts = gTTS(
            text=clean_for_voice,
            lang=lang,
            slow=slow
        )

        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)

        return audio_buffer.getvalue()

    except Exception:
        return None


def call_llm(user_text, user, memories, mode, language, search_context=""):
    if client is None:
        return (
            "⚠️ Groq API key नहीं मिली। "
            "Streamlit Secrets या environment variable में "
            "GROQ_API_KEY डालें।"
        )

    system_prompt = get_system_prompt(
        user,
        memories,
        mode,
        language
    )

    if search_context:
        system_prompt += f"""

Live web search context:
{search_context}

ऊपर दिए live search context का उपयोग करके वर्तमान जानकारी का जवाब दो।
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": user_text
        }
    ]

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.6,
            max_tokens=2048
        )

        answer = response.choices[0].message.content

        if answer:
            return answer.strip()

        return "मुझे अभी कोई जवाब नहीं मिला।"

    except Exception as first_error:
        try:
            response = client.chat.completions.create(
                model=FALLBACK_MODEL,
                messages=messages,
                temperature=0.6,
                max_tokens=2048
            )

            answer = response.choices[0].message.content

            if answer:
                return answer.strip()

            return "मुझे अभी कोई जवाब नहीं मिला।"

        except Exception as second_error:
            return (
                "⚠️ Groq AI से connection में समस्या आई।\n\n"
                f"Primary model error: {str(first_error)}\n\n"
                f"Fallback model error: {str(second_error)}"
            )


def creator_answer():
    return (
        "मुझे अरविंद सिंह ने बनाया है। "
        "वो गाँव दूजासर, श्री मोहनगढ़ से हैं। "
        "मैं उनका personal smart companion हूँ।"
    )


def new_chat():
    conversation_id = create_conversation(
        st.session_state.username,
        "नई चैट"
    )

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = []


def load_conversation(conversation_id):
    rows = get_messages(conversation_id)

    messages = []

    for row in rows:
        messages.append(
            {
                "role": row["role"],
                "content": row["content"]
            }
        )

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = messages


def ensure_session():
    if "username" not in st.session_state:
        query_user = st.query_params.get("user")

        if query_user:
            st.session_state.username = query_user
        else:
            st.session_state.username = DEFAULT_USERNAME
            st.query_params["user"] = DEFAULT_USERNAME

    user = get_user(st.session_state.username)

    if user is None:
        st.session_state.username = DEFAULT_USERNAME
        st.query_params["user"] = DEFAULT_USERNAME
        user = get_user(DEFAULT_USERNAME)

    st.session_state.user = dict(user)

    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "voice_mode" not in st.session_state:
        st.session_state.voice_mode = False

    if "language" not in st.session_state:
        st.session_state.language = "हिंदी"

    if "bot_mode" not in st.session_state:
        st.session_state.bot_mode = "दोस्ताना"

    if "voice_speed" not in st.session_state:
        st.session_state.voice_speed = "सामान्य"

    if "last_audio_hash" not in st.session_state:
        st.session_state.last_audio_hash = ""

    if "file_text" not in st.session_state:
        st.session_state.file_text = ""

    if "file_name" not in st.session_state:
        st.session_state.file_name = ""


ensure_session()


user = st.session_state.user


with st.sidebar:
    st.title("✨ जुगनू AI")

    plan_icon = "👑" if user["plan"] == "VIP PRO" else "🆓"

    st.markdown(
        f"""
        ### 👤 {user['name']}
        **{plan_icon} {user['plan']}**
        """
    )

    st.divider()

    if st.button(
        "➕ नई चैट",
        use_container_width=True
    ):
        new_chat()
        st.rerun()

    if st.button(
        "🚪 लॉगआउट / अकाउंट बदलें",
        use_container_width=True
    ):
        st.session_state.pop("username", None)
        st.session_state.pop("user", None)
        st.query_params.clear()
        st.rerun()

    st.divider()

    st.subheader("📞 Voice Call Mode")

    voice_mode = st.toggle(
        "Voice Call Mode",
        value=st.session_state.voice_mode
    )

    st.session_state.voice_mode = voice_mode

    if voice_mode:
        st.success(
            "📞 Voice mode चालू है। "
            "Assistant के जवाब में audio भी बनाया जाएगा।"
        )

    st.divider()

    st.subheader("⚙️ Settings")

    language = st.selectbox(
        "भाषा",
        [
            "हिंदी",
            "English"
        ],
        index=(
            0
            if st.session_state.language == "हिंदी"
            else 1
        )
    )

    st.session_state.language = language

    bot_mode = st.selectbox(
        "Bot Mode",
        [
            "मारवाड़ी / राजस्थानी",
            "दोस्ताना",
            "शिक्षक",
            "कहानीकार"
        ],
        index=[
            "मारवाड़ी / राजस्थानी",
            "दोस्ताना",
            "शिक्षक",
            "कहानीकार"
        ].index(st.session_state.bot_mode)
    )

    st.session_state.bot_mode = bot_mode

    voice_speed = st.selectbox(
        "Voice Speed",
        [
            "सामान्य",
            "धीमी"
        ],
        index=(
            0
            if st.session_state.voice_speed == "सामान्य"
            else 1
        )
    )

    st.session_state.voice_speed = voice_speed

    st.divider()

    st.subheader("👑 VIP Dashboard")

    all_users = get_all_users()

    st.write(
        f"कुल Users: **{len(all_users)}**"
    )

    user_options = [
        row["username"]
        for row in all_users
    ]

    selected_admin_user = st.selectbox(
        "User",
        user_options,
        index=(
            user_options.index(st.session_state.username)
            if st.session_state.username in user_options
            else 0
        )
    )

    selected_user = get_user(selected_admin_user)

    current_plan = selected_user["plan"]

    new_plan = st.selectbox(
        "Plan बदलें",
        [
            "FREE",
            "VIP PRO"
        ],
        index=(
            0
            if current_plan == "FREE"
            else 1
        )
    )

    if st.button(
        "💾 Plan Save",
        use_container_width=True
    ):
        update_user_plan(
            selected_admin_user,
            new_plan
        )

        if selected_admin_user == st.session_state.username:
            st.session_state.user = dict(
                get_user(selected_admin_user)
            )

        st.success("Plan save हो गया।")
        st.rerun()

    with st.expander("➕ नया User"):
        new_username = st.text_input(
            "Username",
            key="new_username"
        )

        new_name = st.text_input(
            "Name",
            key="new_name"
        )

        new_user_plan = st.selectbox(
            "Initial Plan",
            [
                "FREE",
                "VIP PRO"
            ],
            key="new_user_plan"
        )

        if st.button(
            "User बनाएं",
            use_container_width=True
        ):
            created = create_user(
                new_username,
                new_name,
                new_user_plan
            )

            if created:
                st.success("नया User बन गया।")
                st.rerun()
            else:
                st.error(
                    "Username पहले से मौजूद है "
                    "या जानकारी गलत है।"
                )

    st.divider()

    st.subheader("🧠 Memory Bank")

    memory_input = st.text_area(
        "क्या याद रखना है?",
        placeholder=(
            "उदाहरण: मुझे RAS की तैयारी करनी है।"
        )
    )

    if st.button(
        "💾 Memory Save",
        use_container_width=True
    ):
        if memory_input.strip():
            add_memory(
                st.session_state.username,
                memory_input
            )
            st.success("Memory save हो गई।")
            st.rerun()

    memories = get_memories(
        st.session_state.username
    )

    if memories:
        st.caption(
            f"Saved memories: {len(memories)}"
        )

        for memory in memories[:8]:
            st.write(
                "• " + memory["memory"]
            )

        if st.button(
            "🗑️ सारी Memory Clear",
            use_container_width=True
        ):
            clear_memories(
                st.session_state.username
            )
            st.rerun()

    st.divider()

    st.subheader("⏰ Smart Reminder / Diary")

    note_task = st.text_input(
        "Task / Diary",
        placeholder="आज 7 बजे पढ़ाई करनी है"
    )

    note_time = st.text_input(
        "Reminder Time",
        placeholder="2026-10-03 19:00"
    )

    if st.button(
        "⏰ Reminder Save",
        use_container_width=True
    ):
        if note_task.strip():
            add_note(
                st.session_state.username,
                note_task,
                note_time
            )
            st.success("Reminder save हो गया।")
            st.rerun()

    notes = get_notes(
        st.session_state.username
    )

    if notes:
        for note in notes[:10]:
            status = (
                "✅"
                if note["completed"]
                else "⏳"
            )

            st.markdown(
                f"{status} **{note['task']}**"
            )

            if note["reminder_time"]:
                st.caption(
                    f"⏰ {note['reminder_time']}"
                )

            if not note["completed"]:
                if st.button(
                    "Complete",
                    key=f"complete_{note['id']}"
                ):
                    complete_note(note["id"])
                    st.rerun()

    st.divider()

    st.subheader("🔎 Chat Search")

    chat_search = st.text_input(
        "पुरानी चैट खोजें",
        placeholder="चैट का नाम..."
    )

    conversations = get_conversations(
        st.session_state.username,
        chat_search
    )

    if conversations:
        for conversation in conversations[:15]:
            label = conversation["title"]

            if not label.strip():
                label = "नई चैट"

            if st.button(
                "💬 " + label[:40],
                key=f"conversation_{conversation['id']}",
                use_container_width=True
            ):
                load_conversation(
                    conversation["id"]
                )
                st.rerun()
    else:
        st.caption("अभी कोई पुरानी चैट नहीं है।")


st.title("✨ जुगनू AI")

st.markdown(
    f"""
    ### {user['name']} | पर्सनल स्मार्ट साथी

    **Status:** {user['plan']}
    """
)


if st.session_state.voice_mode:
    st.info(
        "📞 **Voice Call Mode ON** — "
        "जुगनू आपके जवाब का voice भी बनाएगा।"
    )


st.divider()


quick_columns = st.columns(8)

quick_prompts = [
    ("👑 निर्माता", "तुम्हें किसने बनाया?"),
    ("⏰ समय", "अभी का समय क्या है?"),
    ("🌤 मौसम", "आज का मौसम कैसा है?"),
    ("😄 चुटकुला", "एक मजेदार चुटकुला सुनाओ"),
    ("🎨 फोटो", "एक सुंदर राजस्थान की फोटो बनाओ"),
    ("🎯 क्विज़", "मुझे एक सामान्य ज्ञान का quiz दो"),
    ("🍎 सेहत", "स्वस्थ रहने के लिए एक जरूरी सलाह दो"),
    ("💬 मारवाड़ी", "मारवाड़ी में बात करो")
]


for index, (label, prompt) in enumerate(quick_prompts):
    with quick_columns[index]:
        if st.button(
            label,
            use_container_width=True
        ):
            st.session_state.quick_prompt = prompt


st.divider()


audio_file = st.audio_input(
    "🎙️ बोलकर जुगनू से बात करें"
)


if audio_file is not None:
    try:
        audio_bytes = audio_file.getvalue()

        audio_hash = hashlib.sha256(
            audio_bytes
        ).hexdigest()

        if audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = audio_hash

            with st.spinner("🎧 आपकी आवाज समझ रहा हूँ..."):
                transcript = transcribe_audio(
                    audio_file
                )

            if transcript and not transcript.startswith(
                "Voice transcription error"
            ):
                st.session_state.quick_prompt = transcript
                st.success(
                    f"आपने कहा: {transcript}"
                )
                st.rerun()
            else:
                st.error(transcript)

    except Exception as e:
        st.error(
            f"Audio process error: {str(e)}"
        )


st.divider()


uploaded_file = st.file_uploader(
    "📚 PDF / TXT पढ़ने के लिए upload करें",
    type=[
        "pdf",
        "txt"
    ]
)


if uploaded_file is not None:
    if (
        st.session_state.file_name
        != uploaded_file.name
    ):
        st.session_state.file_name = uploaded_file.name

        if uploaded_file.name.lower().endswith(".pdf"):
            st.session_state.file_text = extract_pdf_text(
                uploaded_file
            )
        else:
            st.session_state.file_text = extract_txt_text(
                uploaded_file
            )

    if st.session_state.file_text:
        with st.expander(
            f"📖 {uploaded_file.name} पढ़ें",
            expanded=False
        ):
            preview_text = st.session_state.file_text

            if len(preview_text) > 12000:
                preview_text = preview_text[:12000]

            st.text_area(
                "File Content",
                preview_text,
                height=350
            )


image_file = st.file_uploader(
    "🖼️ Image Preview",
    type=[
        "png",
        "jpg",
        "jpeg",
        "webp"
    ],
    key="image_upload"
)


if image_file is not None:
    try:
        image = Image.open(image_file)

        st.image(
            image,
            caption=image_file.name,
            use_container_width=True
        )

    except Exception as e:
        st.error(
            f"Image पढ़ने में समस्या: {str(e)}"
        )


st.divider()


if st.session_state.conversation_id is None:
    st.session_state.conversation_id = create_conversation(
        st.session_state.username,
        "नई चैट"
    )


for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]

    with st.chat_message(role):
        st.markdown(content)


if "quick_prompt" in st.session_state:
    user_input = st.session_state.pop(
        "quick_prompt"
    )
else:
    user_input = st.chat_input(
        "जुगनू से कुछ भी पूछें..."
    )


if user_input:
    user_input = normalize_user_text(
        user_input
    )

    if user_input:
        if not st.session_state.messages:
            title = user_input[:70]

            update_conversation_title(
                st.session_state.conversation_id,
                title
            )

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_input
            }
        )

        add_message(
            st.session_state.conversation_id,
            "user",
            user_input
        )

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()

            with st.spinner("✨ जुगनू सोच रहा है..."):
                if is_creator_question(user_input):
                    answer = creator_answer()

                elif is_photo_request(user_input):
                    photo_url = get_photo_url(
                        user_input
                    )

                    answer = (
                        "🎨 आपकी फोटो तैयार है:\n\n"
                        + photo_url
                    )

                else:
                    search_context = ""

                    if should_search_web(user_input):
                        with st.spinner(
                            "🌐 Live information खोज रहा हूँ..."
                        ):
                            search_context = live_search(
                                user_input,
                                max_results=5
                            )

                    memories = get_memories(
                        st.session_state.username
                    )

                    answer = call_llm(
                        user_input,
                        user,
                        memories,
                        st.session_state.bot_mode,
                        st.session_state.language,
                        search_context
                    )

            response_placeholder.markdown(
                answer
            )

            if (
                is_photo_request(user_input)
                and "https://image.pollinations.ai/" in answer
            ):
                photo_url = answer.split(
                    "https://image.pollinations.ai/",
                    1
                )[1]

                photo_url = (
                    "https://image.pollinations.ai/"
                    + photo_url.split()[0]
                )

                try:
                    st.image(
                        photo_url,
                        caption="🎨 जुगनू AI Image",
                        use_container_width=True
                    )
                except Exception:
                    pass

            if st.session_state.voice_mode:
                audio_data = generate_tts(
                    answer,
                    st.session_state.language,
                    st.session_state.voice_speed
                )

                if audio_data:
                    st.audio(
                        audio_data,
                        format="audio/mp3",
                        autoplay=True
                    )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        add_message(
            st.session_state.conversation_id,
            "assistant",
            answer
        )

        st.rerun()


st.divider()


with st.expander(
    "ℹ️ जुगनू AI System Status"
):
    if client:
        st.success(
            "🟢 Groq API connected"
        )

        st.write(
            f"Main Model: `{DEFAULT_MODEL}`"
        )

        st.write(
            f"Fallback Model: `{FALLBACK_MODEL}`"
        )

        st.write(
            f"Voice Model: `{WHISPER_MODEL}`"
        )

    else:
        st.error(
            "🔴 GROQ_API_KEY configured नहीं है।"
        )

    st.write(
        f"Logged in user: `{st.session_state.username}`"
    )

    st.write(
        f"Plan: `{user['plan']}`"
    )

    st.write(
        f"Conversation ID: `{st.session_state.conversation_id}`"
    )
