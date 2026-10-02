import os
import io
import re
import json
import time
import base64
import sqlite3
import tempfile
from datetime import datetime, timedelta

import streamlit as st
from groq import Groq
from gtts import gTTS
from pypdf import PdfReader
from duckduckgo_search import DDGS
from PIL import Image


APP_TITLE = "जुगनू AI"
DB_PATH = "jugnu_data.db"
DEFAULT_USER_ID = "arvind"
DEFAULT_NAME = "अरविंद सिंह"
DEFAULT_PLAN = "VIP PRO"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"


st.set_page_config(
    page_title="जुगनू AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            language TEXT NOT NULL DEFAULT 'Hindi',
            bot_mode TEXT NOT NULL DEFAULT 'दोस्ताना',
            voice_speed TEXT NOT NULL DEFAULT 'सामान्य',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
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
            user_id TEXT NOT NULL,
            task TEXT NOT NULL,
            reminder_time TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            fact TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        "SELECT id FROM users WHERE id = ?",
        (DEFAULT_USER_ID,),
    )

    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO users
            (id, name, plan, language, bot_mode, voice_speed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_USER_ID,
                DEFAULT_NAME,
                DEFAULT_PLAN,
                "Hindi",
                "दोस्ताना",
                "सामान्य",
                datetime.now().isoformat(),
            ),
        )

    conn.commit()
    conn.close()


def get_user():
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_settings(language, bot_mode, voice_speed, plan=None):
    conn = get_db()

    if plan is None:
        conn.execute(
            """
            UPDATE users
            SET language = ?, bot_mode = ?, voice_speed = ?
            WHERE id = ?
            """,
            (language, bot_mode, voice_speed, DEFAULT_USER_ID),
        )
    else:
        conn.execute(
            """
            UPDATE users
            SET language = ?, bot_mode = ?, voice_speed = ?, plan = ?
            WHERE id = ?
            """,
            (
                language,
                bot_mode,
                voice_speed,
                plan,
                DEFAULT_USER_ID,
            ),
        )

    conn.commit()
    conn.close()


def create_conversation(title="नई बातचीत"):
    conn = get_db()
    now = datetime.now().isoformat()

    cur = conn.execute(
        """
        INSERT INTO conversations
        (user_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (DEFAULT_USER_ID, title[:80], now, now),
    )

    conversation_id = cur.lastrowid
    conn.commit()
    conn.close()
    return conversation_id


def get_conversations():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT *
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (DEFAULT_USER_ID,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_messages(conversation_id):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT *
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_message(conversation_id, role, content):
    conn = get_db()
    now = datetime.now().isoformat()

    conn.execute(
        """
        INSERT INTO messages
        (conversation_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (conversation_id, role, content, now),
    )

    conn.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE id = ?
        """,
        (now, conversation_id),
    )

    conn.commit()
    conn.close()


def rename_conversation(conversation_id, title):
    conn = get_db()

    conn.execute(
        """
        UPDATE conversations
        SET title = ?
        WHERE id = ? AND user_id = ?
        """,
        (title[:80], conversation_id, DEFAULT_USER_ID),
    )

    conn.commit()
    conn.close()


def add_memory(fact):
    fact = fact.strip()

    if not fact:
        return

    conn = get_db()

    conn.execute(
        """
        INSERT INTO user_memories
        (user_id, fact, created_at)
        VALUES (?, ?, ?)
        """,
        (
            DEFAULT_USER_ID,
            fact,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def get_memories():
    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM user_memories
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (DEFAULT_USER_ID,),
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def clear_memories():
    conn = get_db()

    conn.execute(
        """
        DELETE FROM user_memories
        WHERE user_id = ?
        """,
        (DEFAULT_USER_ID,),
    )

    conn.commit()
    conn.close()


def add_note(task, reminder_time):
    task = task.strip()
    reminder_time = reminder_time.strip()

    if not task or not reminder_time:
        return

    conn = get_db()

    conn.execute(
        """
        INSERT INTO notes
        (user_id, task, reminder_time, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            DEFAULT_USER_ID,
            task,
            reminder_time,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def get_notes():
    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM notes
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (DEFAULT_USER_ID,),
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def delete_note(note_id):
    conn = get_db()

    conn.execute(
        """
        DELETE FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, DEFAULT_USER_ID),
    )

    conn.commit()
    conn.close()


def get_all_users():
    conn = get_db()

    rows = conn.execute(
        """
        SELECT id, name, plan, created_at
        FROM users
        ORDER BY created_at ASC
        """
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_api_key():
    key = os.getenv("GROQ_API_KEY", "").strip()

    if key:
        return key

    try:
        key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        key = ""

    return str(key).strip()


def get_groq_client():
    api_key = get_api_key()

    if not api_key:
        return None

    try:
        return Groq(api_key=api_key)
    except Exception:
        return None


def safe_text(value):
    if value is None:
        return ""

    return str(value).strip()


def detect_photo_request(text):
    lower = text.lower()

    keywords = [
        "photo",
        "image",
        "picture",
        "फोटो",
        "तस्वीर",
        "चित्र",
        "इमेज",
        "बना दो",
        "बना दे",
        "बनाओ",
        "generate image",
        "generate photo",
    ]

    return any(word in lower for word in keywords)


def create_pollinations_url(prompt):
    cleaned = re.sub(r"\s+", " ", prompt.strip())

    if not cleaned:
        cleaned = "beautiful realistic Indian Rajasthan landscape"

    encoded = (
        cleaned.replace(" ", "%20")
        .replace("/", "%2F")
        .replace("?", "%3F")
        .replace("#", "%23")
    )

    return f"https://image.pollinations.ai/prompt/{encoded}"


def ddg_search(query, max_results=5):
    results = []

    try:
        with DDGS() as ddgs:
            for item in ddgs.text(
                query,
                max_results=max_results,
            ):
                title = safe_text(item.get("title"))
                body = safe_text(item.get("body"))
                href = safe_text(item.get("href"))

                if title or body:
                    results.append(
                        {
                            "title": title,
                            "body": body,
                            "href": href,
                        }
                    )
    except Exception:
        return []

    return results


def looks_like_live_search_request(text):
    lower = text.lower()

    terms = [
        "latest",
        "today",
        "current",
        "news",
        "live",
        "अभी",
        "आज",
        "ताजा",
        "ताज़ा",
        "लेटेस्ट",
        "न्यूज़",
        "समाचार",
        "मौसम",
        "weather",
        "search",
        "खोज",
        "कौन है",
        "क्या हुआ",
    ]

    return any(term in lower for term in terms)


def build_search_context(results):
    if not results:
        return ""

    parts = []

    for index, result in enumerate(results, start=1):
        title = result.get("title", "")
        body = result.get("body", "")
        href = result.get("href", "")

        parts.append(
            f"[{index}] {title}\n"
            f"{body}\n"
            f"Source: {href}"
        )

    return "\n\n".join(parts)


def get_memory_context():
    memories = get_memories()

    if not memories:
        return ""

    return "\n".join(
        f"- {item['fact']}"
        for item in memories[:30]
    )


def is_marwari_request(text):
    lower = text.lower()

    terms = [
        "मारवाड़ी",
        "मारवाड़ी",
        "राजस्थानी",
        "marwari",
        "rajasthani",
        "mhare",
        "mharo",
        "mhari",
    ]

    return any(term in lower for term in terms)


def creator_question(text):
    lower = text.lower()

    creator_terms = [
        "किसने बनाया",
        "किसने बनायो",
        "किसने बनाया है",
        "creator",
        "who made you",
        "who created you",
        "तुम्हें किसने बनाया",
        "तने किसने बनायो",
        "जुगनू किसने बनाया",
    ]

    return any(term in lower for term in creator_terms)


def get_creator_response():
    return (
        "म्हाने अरविंद सिंह ने बनायो है, जो गाँव दूजासर, "
        "श्री मोहनगढ़ से हैं। ✨"
    )


def make_system_prompt(user, memories, search_context):
    language = user.get("language", "Hindi")
    bot_mode = user.get("bot_mode", "दोस्ताना")

    mode_instruction = {
        "मारवाड़ी / राजस्थानी": (
            "उत्तर शुद्ध और स्वाभाविक मारवाड़ी/राजस्थानी में दें। "
            "बहुत लंबा उत्तर न दें।"
        ),
        "दोस्ताना": (
            "यूज़र से गर्मजोशी और दोस्ताना अंदाज में बात करें।"
        ),
        "शिक्षक": (
            "उत्तर शिक्षक की तरह स्पष्ट, सरल और उदाहरण सहित दें।"
        ),
        "कहानीकार": (
            "जहाँ उचित हो, रोचक कहानीकार शैली अपनाएँ।"
        ),
    }.get(bot_mode, "दोस्ताना शैली रखें।")

    if language == "English":
        language_instruction = (
            "Answer primarily in clear English unless the user asks for another language."
        )
    else:
        language_instruction = (
            "Answer primarily in natural Hindi unless the user asks for another language."
        )

    memory_instruction = (
        f"User memory bank:\n{memories}"
        if memories
        else "User memory bank is currently empty."
    )

    search_instruction = (
        f"Live web search results:\n{search_context}"
        if search_context
        else "No live search results were provided."
    )

    return f"""
You are Jugnu AI, a personal smart companion created for Arvind Singh.

Important creator fact:
If asked who created you, say that Arvind Singh from Gaon Doojasar, Shri Mohangarh created you.

Language:
{language_instruction}

Bot mode:
{mode_instruction}

Marwari requirement:
If the user explicitly asks for Marwari/Rajasthani or the current bot mode is
Marwari/Rajasthani, reply in natural, sweet Marwari/Rajasthani.
For ordinary small conversational requests, keep it to about 1-2 lines.

Be useful, direct, honest, and do not invent facts.
If live search information is supplied, use it carefully and distinguish search
results from established knowledge.

{memory_instruction}

{search_instruction}
""".strip()


def call_llm(user_text, history, user, search_context=""):
    client = get_groq_client()

    if client is None:
        return (
            "Groq API key नहीं मिली। कृपया GROQ_API_KEY को Streamlit secrets "
            "या environment variable में सेट करें।"
        )

    if creator_question(user_text):
        return get_creator_response()

    if detect_photo_request(user_text):
        image_url = create_pollinations_url(user_text)
        return (
            "आपके लिए फोटो तैयार करने का लिंक:\n\n"
            f"{image_url}"
        )

    memories = get_memory_context()

    system_prompt = make_system_prompt(
        user=user,
        memories=memories,
        search_context=search_context,
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    for item in history[-20:]:
        role = item.get("role")

        if role not in ["user", "assistant"]:
            continue

        content = safe_text(item.get("content"))

        if not content:
            continue

        messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    messages.append(
        {
            "role": "user",
            "content": user_text,
        }
    )

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1200,
        )

        answer = response.choices[0].message.content

        if answer:
            return answer.strip()

    except Exception as primary_error:
        try:
            response = client.chat.completions.create(
                model=FALLBACK_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1200,
            )

            answer = response.choices[0].message.content

            if answer:
                return answer.strip()

        except Exception as fallback_error:
            return (
                "अभी AI सेवा से उत्तर नहीं मिल पाया। "
                f"मुख्य मॉडल त्रुटि: {primary_error}. "
                f"Fallback मॉडल त्रुटि: {fallback_error}"
            )

    return "मुझे अभी कोई उत्तर नहीं मिला।"


def transcribe_audio(audio_value):
    client = get_groq_client()

    if client is None:
        return "Groq API key उपलब्ध नहीं है।"

    try:
        if hasattr(audio_value, "getvalue"):
            audio_bytes = audio_value.getvalue()
        elif isinstance(audio_value, bytes):
            audio_bytes = audio_value
        else:
            return ""

        if not audio_bytes:
            return ""

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "voice_input.wav"

        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3-turbo",
            response_format="text",
        )

        if isinstance(transcription, str):
            return transcription.strip()

        if hasattr(transcription, "text"):
            return safe_text(transcription.text)

        return safe_text(transcription)

    except Exception as error:
        return f"Voice transcription error: {error}"


def generate_tts(text, language):
    try:
        clean_text = re.sub(
            r"https?://\S+",
            "",
            text,
        ).strip()

        if not clean_text:
            clean_text = "नमस्ते, मैं जुगनू हूँ।"

        tts_language = "en" if language == "English" else "hi"

        slow = (
            st.session_state.get("voice_speed", "सामान्य")
            == "धीमी"
        )

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".mp3",
            delete=False,
        )

        temp_path = temp_file.name
        temp_file.close()

        tts = gTTS(
            text=clean_text[:4000],
            lang=tts_language,
            slow=slow,
        )

        tts.save(temp_path)

        with open(temp_path, "rb") as audio_file:
            audio_bytes = audio_file.read()

        try:
            os.remove(temp_path)
        except Exception:
            pass

        return audio_bytes

    except Exception:
        return None


def show_audio_autoplay(text, language):
    audio_bytes = generate_tts(
        text=text,
        language=language,
    )

    if audio_bytes:
        st.audio(
            audio_bytes,
            format="audio/mp3",
            autoplay=True,
        )


def extract_pdf_text(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        pages = []

        for page in reader.pages:
            page_text = page.extract_text() or ""

            if page_text.strip():
                pages.append(page_text)

        return "\n\n".join(pages)

    except Exception as error:
        return f"PDF पढ़ने में समस्या: {error}"


def extract_txt_text(uploaded_file):
    try:
        raw = uploaded_file.read()

        for encoding in ["utf-8", "utf-8-sig", "utf-16", "latin-1"]:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw.decode("utf-8", errors="ignore")

    except Exception as error:
        return f"TXT पढ़ने में समस्या: {error}"


def process_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return ""

    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return extract_pdf_text(uploaded_file)

    if name.endswith(".txt"):
        return extract_txt_text(uploaded_file)

    return ""


def initialize_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = True

    if "user_id" not in st.session_state:
        st.session_state.user_id = DEFAULT_USER_ID

    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None

    if "voice_call" not in st.session_state:
        st.session_state.voice_call = False

    if "voice_speed" not in st.session_state:
        st.session_state.voice_speed = "सामान्य"

    if "last_voice_text" not in st.session_state:
        st.session_state.last_voice_text = ""

    if "last_audio_answer" not in st.session_state:
        st.session_state.last_audio_answer = None

    if "uploaded_context" not in st.session_state:
        st.session_state.uploaded_context = ""

    if "search_chat" not in st.session_state:
        st.session_state.search_chat = ""

    query_user = st.query_params.get("user")

    if query_user == DEFAULT_USER_ID:
        st.session_state.logged_in = True
        st.session_state.user_id = DEFAULT_USER_ID

    st.query_params["user"] = DEFAULT_USER_ID


def ensure_conversation():
    if st.session_state.conversation_id is None:
        st.session_state.conversation_id = create_conversation(
            "नई बातचीत"
        )


def start_new_chat():
    st.session_state.conversation_id = create_conversation(
        "नई बातचीत"
    )
    st.session_state.last_voice_text = ""
    st.session_state.last_audio_answer = None


def load_conversation(conversation_id):
    st.session_state.conversation_id = int(conversation_id)
    st.session_state.last_voice_text = ""
    st.session_state.last_audio_answer = None


def handle_user_message(text, source="chat"):
    text = safe_text(text)

    if not text:
        return

    ensure_conversation()

    current_messages = get_messages(
        st.session_state.conversation_id
    )

    if len(current_messages) == 0:
        rename_conversation(
            st.session_state.conversation_id,
            text,
        )

    add_message(
        st.session_state.conversation_id,
        "user",
        text,
    )

    search_context = ""

    if looks_like_live_search_request(text):
        search_results = ddg_search(
            text,
            max_results=5,
        )
        search_context = build_search_context(
            search_results
        )

    user = get_user()

    answer = call_llm(
        user_text=text,
        history=current_messages,
        user=user,
        search_context=search_context,
    )

    if source == "voice":
        st.session_state.last_voice_text = text

    add_message(
        st.session_state.conversation_id,
        "assistant",
        answer,
    )

    st.session_state.last_audio_answer = answer

    if st.session_state.voice_call:
        st.session_state.autoplay_answer = True
    else:
        st.session_state.autoplay_answer = False


def render_sidebar():
    user = get_user()

    with st.sidebar:
        st.markdown(
            """
            <div style="
                padding:14px;
                border-radius:16px;
                background:linear-gradient(135deg,#fff4c4,#ffe082);
                border:1px solid #f0c84b;
                margin-bottom:12px;
            ">
                <div style="font-size:19px;font-weight:700;">
                    👤 अरविंद सिंह
                </div>
                <div style="margin-top:5px;font-size:15px;">
                    👑 VIP PRO
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "➕ नई चैट",
                use_container_width=True,
            ):
                start_new_chat()
                st.rerun()

        with col2:
            if st.button(
                "🚪 लॉगआउट",
                use_container_width=True,
            ):
                st.session_state.logged_in = False
                st.query_params.clear()
                st.session_state.logged_in = True
                st.query_params["user"] = DEFAULT_USER_ID
                st.rerun()

        st.divider()

        voice_label = (
            "📞 वॉयस कॉल बंद करें"
            if st.session_state.voice_call
            else "📞 वॉयस कॉल मोड"
        )

        if st.button(
            voice_label,
            use_container_width=True,
        ):
            st.session_state.voice_call = (
                not st.session_state.voice_call
            )

            if st.session_state.voice_call:
                st.session_state.autoplay_answer = True
            else:
                st.session_state.autoplay_answer = False

            st.rerun()

        st.divider()

        with st.expander(
            "💰 कमाई व VIP डैशबोर्ड",
            expanded=True,
        ):
            users = get_all_users()

            st.metric(
                "कुल यूज़र",
                len(users),
            )

            current_plan = user.get(
                "plan",
                DEFAULT_PLAN,
            )

            selected_plan = st.selectbox(
                "प्लान अपग्रेड",
                ["free", "VIP PRO"],
                index=(
                    1
                    if current_plan.upper() == "VIP PRO"
                    else 0
                ),
                key="sidebar_plan",
            )

            if st.button(
                "💾 प्लान सेव करें",
                use_container_width=True,
            ):
                update_user_settings(
                    user.get("language", "Hindi"),
                    user.get("bot_mode", "दोस्ताना"),
                    user.get("voice_speed", "सामान्य"),
                    selected_plan,
                )
                st.success("प्लान सेव हो गया।")
                st.rerun()

            for item in users:
                st.caption(
                    f"👤 {item['name']} — {item['plan']}"
                )

        with st.expander(
            "⚙️ सेटिंग्स",
            expanded=True,
        ):
            language = st.selectbox(
                "भाषा",
                ["Hindi", "English"],
                index=(
                    1
                    if user.get("language") == "English"
                    else 0
                ),
                key="settings_language",
            )

            bot_modes = [
                "मारवाड़ी / राजस्थानी",
                "दोस्ताना",
                "शिक्षक",
                "कहानीकार",
            ]

            current_mode = user.get(
                "bot_mode",
                "दोस्ताना",
            )

            mode_index = (
                bot_modes.index(current_mode)
                if current_mode in bot_modes
                else 1
            )

            bot_mode = st.selectbox(
                "Bot Mode",
                bot_modes,
                index=mode_index,
                key="settings_bot_mode",
            )

            voice_speed = st.selectbox(
                "Voice speed",
                ["सामान्य", "धीमी"],
                index=(
                    1
                    if user.get("voice_speed") == "धीमी"
                    else 0
                ),
                key="settings_voice_speed",
            )

            if st.button(
                "💾 सेटिंग्स सेव करें",
                use_container_width=True,
            ):
                update_user_settings(
                    language,
                    bot_mode,
                    voice_speed,
                )

                st.session_state.voice_speed = voice_speed

                st.success("सेटिंग्स सेव हो गईं।")
                st.rerun()

        with st.expander(
            "🧠 याददाश्त",
            expanded=False,
        ):
            memory_text = st.text_area(
                "यूज़र के बारे में क्या याद रखना है?",
                placeholder="उदाहरण: मुझे RAS की तैयारी करनी है।",
                key="memory_text",
            )

            if st.button(
                "🧠 याद रखें",
                use_container_width=True,
            ):
                if memory_text.strip():
                    add_memory(memory_text)
                    st.success("याददाश्त में सेव हो गया।")
                    st.rerun()

            if st.button(
                "🗑️ पूरी याददाश्त साफ करें",
                use_container_width=True,
            ):
                clear_memories()
                st.success("याददाश्त साफ हो गई।")
                st.rerun()

            memories = get_memories()

            if memories:
                for memory in memories:
                    st.info(
                        f"🧠 {memory['fact']}"
                    )
            else:
                st.caption(
                    "अभी कोई memory saved नहीं है।"
                )

        with st.expander(
            "⏰ स्मार्ट रिमाइंडर व डायरी",
            expanded=False,
        ):
            note_task = st.text_input(
                "काम",
                placeholder="उदाहरण: RAS पढ़ाई",
                key="note_task",
            )

            note_time = st.text_input(
                "समय",
                placeholder="उदाहरण: 06:30 PM",
                key="note_time",
            )

            if st.button(
                "⏰ रिमाइंडर सेव करें",
                use_container_width=True,
            ):
                if note_task.strip() and note_time.strip():
                    add_note(
                        note_task,
                        note_time,
                    )
                    st.success(
                        "रिमाइंडर सेव हो गया।"
                    )
                    st.rerun()

            notes = get_notes()

            if notes:
                for note in notes:
                    ncol1, ncol2 = st.columns(
                        [4, 1]
                    )

                    with ncol1:
                        st.write(
                            f"⏰ {note['task']}"
                        )
                        st.caption(
                            note["reminder_time"]
                        )

                    with ncol2:
                        if st.button(
                            "✕",
                            key=f"delete_note_{note['id']}",
                        ):
                            delete_note(note["id"])
                            st.rerun()
            else:
                st.caption(
                    "अभी कोई reminder नहीं है।"
                )

        st.divider()

        st.subheader("🔍 चैट खोजें")

        search_text = st.text_input(
            "Search",
            placeholder="चैट में खोजें...",
            label_visibility="collapsed",
            key="chat_search_box",
        )

        st.subheader("💬 पुरानी बातचीत")

        conversations = get_conversations()

        if search_text.strip():
            filtered = []

            conn = get_db()

            rows = conn.execute(
                """
                SELECT DISTINCT
                    c.id,
                    c.title,
                    c.created_at,
                    c.updated_at
                FROM conversations c
                LEFT JOIN messages m
                    ON c.id = m.conversation_id
                WHERE c.user_id = ?
                  AND (
                      c.title LIKE ?
                      OR m.content LIKE ?
                  )
                ORDER BY c.updated_at DESC
                """,
                (
                    DEFAULT_USER_ID,
                    f"%{search_text}%",
                    f"%{search_text}%",
                ),
            ).fetchall()

            conn.close()

            filtered = [dict(row) for row in rows]
            conversations = filtered

        if not conversations:
            st.caption(
                "कोई पुरानी बातचीत नहीं मिली।"
            )

        for conversation in conversations[:50]:
            title = conversation["title"]

            if len(title) > 32:
                title = title[:32] + "..."

            if st.button(
                f"💬 {title}",
                key=f"conversation_{conversation['id']}",
                use_container_width=True,
            ):
                load_conversation(
                    conversation["id"]
                )
                st.rerun()


def render_header():
    st.markdown(
        """
        <div style="
            padding:18px 20px;
            border-radius:20px;
            background:linear-gradient(135deg,#fff7d6,#ffe8a3);
            border:1px solid #efcf70;
            margin-bottom:18px;
        ">
            <div style="
                font-size:29px;
                font-weight:800;
                color:#7a4e00;
            ">
                ✨ जुगनू AI
            </div>
            <div style="
                font-size:16px;
                margin-top:4px;
                color:#654c1d;
            ">
                अरविंद सिंह | पर्सनल स्मार्ट साथी
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_call_banner():
    if st.session_state.voice_call:
        st.markdown(
            """
            <div style="
                padding:15px;
                border-radius:18px;
                background:linear-gradient(135deg,#dfffe7,#b9f6ca);
                border:1px solid #64c77a;
                text-align:center;
                margin-bottom:15px;
            ">
                <div style="font-size:24px;font-weight:800;">
                    📞 वॉयस कॉल मोड सक्रिय
                </div>
                <div style="margin-top:5px;">
                    जुगनू आपकी आवाज़ सुनने और जवाब बोलने के लिए तैयार है।
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_quick_buttons():
    st.markdown(
        "### ⚡ Quick Suggestions"
    )

    suggestions = [
        ("👑 निर्माता", "तुम्हें किसने बनाया?"),
        ("⏰ समय", "अभी समय क्या है?"),
        ("🌤 मौसम", "आज का मौसम कैसा है?"),
        ("😄 चुटकुला", "एक मजेदार चुटकुला सुनाओ"),
        ("🎨 फोटो", "राजस्थान के रेगिस्तान की एक सुंदर फोटो बनाओ"),
        ("🎯 क्विज़", "मेरे लिए सामान्य ज्ञान का एक क्विज़ शुरू करो"),
        ("🍎 सेहत", "स्वस्थ रहने के लिए आज एक आसान टिप बताओ"),
        ("💬 मारवाड़ी", "मारवाड़ी में म्हारे सूं बात करो"),
    ]

    columns = st.columns(4)

    for index, (label, prompt) in enumerate(
        suggestions
    ):
        with columns[index % 4]:
            if st.button(
                label,
                key=f"quick_{index}",
                use_container_width=True,
            ):
                handle_user_message(prompt)
                st.rerun()


def render_audio_mic():
    st.markdown(
        "### 🎙️ बोलकर बात करें"

    )

    st.caption(
        "अपनी आवाज़ रिकॉर्ड करें — Whisper large v3 turbo से transcription होगी।"
    )

    audio_value = st.audio_input(
        "🎙️ आवाज़ रिकॉर्ड करें",
        key="voice_input",
    )

    if audio_value is not None:
        audio_identifier = getattr(
            audio_value,
            "size",
            None,
        )

        previous_identifier = st.session_state.get(
            "processed_audio_identifier"
        )

        if audio_identifier != previous_identifier:
            st.session_state.processed_audio_identifier = (
                audio_identifier
            )

            with st.spinner(
                "🎧 आवाज़ को समझ रहा हूँ..."
            ):
                transcript = transcribe_audio(
                    audio_value
                )

            if transcript:
                st.info(
                    f"📝 आपने कहा: {transcript}"
                )

                if not transcript.lower().startswith(
                    "voice transcription error"
                ):
                    handle_user_message(
                        transcript,
                        source="voice",
                    )
                    st.rerun()


def render_file_box():
    st.markdown(
        "### 📎 File & Image Box"
    )

    uploaded_file = st.file_uploader(
        "PDF/TXT या Image attach करें",
        type=[
            "pdf",
            "txt",
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        key="main_file_uploader",
    )

    if uploaded_file is None:
        return

    file_name = uploaded_file.name.lower()

    if file_name.endswith(
        (".png", ".jpg", ".jpeg", ".webp")
    ):
        try:
            image = Image.open(uploaded_file)

            st.image(
                image,
                caption=uploaded_file.name,
                use_container_width=True,
            )

            st.session_state.uploaded_context = (
                f"यूज़र ने image attach की है: {uploaded_file.name}"
            )

        except Exception as error:
            st.error(
                f"Image preview error: {error}"
            )

    elif file_name.endswith(
        (".pdf", ".txt")
    ):
        text = process_uploaded_file(
            uploaded_file
        )

        if text:
            st.session_state.uploaded_context = text

            st.success(
                f"📄 {uploaded_file.name} पढ़ लिया गया।"
            )

            preview = text[:6000]

            with st.expander(
                "📖 Document text देखें",
                expanded=False,
            ):
                st.text_area(
                    "Extracted text",
                    preview,
                    height=250,
                    disabled=True,
                    label_visibility="collapsed",
                )

            if st.button(
                "🤖 इस document के बारे में पूछें",
                use_container_width=True,
            ):
                handle_user_message(
                    "Attached document का सारांश और मुख्य बातें बताओ:\n\n"
                    + text[:12000]
                )
                st.rerun()
        else:
            st.warning(
                "Document से text नहीं निकाला जा सका।"
            )


def render_chat():
    ensure_conversation()

    messages = get_messages(
        st.session_state.conversation_id
    )

    if not messages:
        st.markdown(
            """
            <div style="
                text-align:center;
                padding:30px 10px;
                color:#777;
            ">
                <div style="font-size:48px;">✨</div>
                <h3>नमस्ते अरविंद जी!</h3>
                <p>मैं जुगनू हूँ — आपका पर्सनल स्मार्ट साथी।</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    for message in messages:
        role = message["role"]

        with st.chat_message(
            "user" if role == "user" else "assistant"
        ):
            content = message["content"]

            image_urls = re.findall(
                r"https://image\.pollinations\.ai/prompt/\S+",
                content,
            )

            if image_urls:
                clean_content = re.sub(
                    r"https://image\.pollinations\.ai/prompt/\S+",
                    "",
                    content,
                ).strip()

                if clean_content:
                    st.markdown(clean_content)

                for image_url in image_urls:
                    st.image(
                        image_url,
                        caption="🎨 Generated Image",
                        use_container_width=True,
                    )
            else:
                st.markdown(content)

    if (
        st.session_state.get("voice_call")
        and st.session_state.get("autoplay_answer")
        and st.session_state.get("last_audio_answer")
    ):
        user = get_user()

        st.markdown(
            "🔊 **जुगनू बोल रहा है...**"
        )

        show_audio_autoplay(
            st.session_state.last_audio_answer,
            user.get("language", "Hindi"),
        )

        st.session_state.autoplay_answer = False


def render_chat_input():
    prompt = st.chat_input(
        "जुगनू से कुछ पूछिए..."
    )

    if prompt:
        if st.session_state.get(
            "uploaded_context"
        ):
            prompt_with_context = (
                f"{prompt}\n\n"
                "Attached document context:\n"
                f"{st.session_state.uploaded_context[:12000]}"
            )
            st.session_state.uploaded_context = ""
        else:
            prompt_with_context = prompt

        handle_user_message(
            prompt_with_context
        )
        st.rerun()


def main():
    init_db()
    initialize_session()

    user = get_user()

    if not user:
        st.error(
            "Default user initialize नहीं हो पाया।"
        )
        st.stop()

    render_sidebar()

    render_header()

    render_call_banner()

    render_quick_buttons()

    st.divider()

    left, right = st.columns(
        [1.25, 1],
        gap="large",
    )

    with left:
        render_audio_mic()

    with right:
        render_file_box()

    st.divider()

    render_chat()

    render_chat_input()


if __name__ == "__main__":
    main()
