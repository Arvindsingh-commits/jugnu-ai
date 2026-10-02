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

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# --- Mobile-Friendly UI & CSS ---
st.markdown("""

""", unsafe_allow_html=True)

# --- SQLite Database Setup ---
DB_FILE = "jugnu_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name TEXT,
            pin TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            note TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO users VALUES ('arvind', 'अरविंद सिंह', '1234')")
    cursor.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'Admin', '0000')")
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
if "messages" not in st.session_state:
    st.session_state.messages = []
if "personal_notes" not in st.session_state:
    st.session_state.personal_notes = []

# --- 1. Login Screen ---
if not st.session_state.logged_in_user:
    st.title("✨ JUGNU AI Assistant")
    
    # Language Selection on Login Page
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
                user = db_query("SELECT name, pin FROM users WHERE username = ?", (uname,), fetchone=True)
                if user and user[1] == upin:
                    st.session_state.logged_in_user = uname
                    st.session_state.logged_in_name = user[0]
                    history = db_query("SELECT role, content FROM chat_history WHERE username = ? ORDER BY id ASC", (uname,), fetchall=True)
                    if history:
                        st.session_state.messages = [{"role": r, "content": c} for r, c in history]
                    else:
                        welcome_txt = f"नमस्ते {user[0]} जी! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?" if is_hi else f"Hello {user[0]}! I am JUGNU AI. How can I help you today?"
                        st.session_state.messages = [{"role": "assistant", "content": welcome_txt}]
                    notes = db_query("SELECT note FROM notes WHERE username = ?", (uname,), fetchall=True)
                    st.session_state.personal_notes = [n[0] for n in notes] if notes else []
                    st.success("लॉगिन सफल रहा!" if is_hi else "Login successful!")
                    st.rerun()
                else:
                    st.error("ग़लत यूज़रनेम या पासवर्ड!" if is_hi else "Invalid username or password!")
    
    with tab_signup:
        with st.form("signup_form"):
            new_name = st.text_input("आपका पूरा नाम:" if is_hi else "Full Name:", placeholder="उदा. अरविंद सिंह").strip()
            new_uname = st.text_input("नया यूज़रनेम चुनें:" if is_hi else "Choose Username:", placeholder="उदा. arvind123").strip().lower()
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
                        db_query("INSERT INTO users VALUES (?, ?, ?)", (new_uname, new_name, new_pin), commit=True)
                        st.session_state.logged_in_user = new_uname
                        st.session_state.logged_in_name = new_name
                        welcome_txt = f"नमस्ते {new_name} जी! आपका खाता बन गया है। कहिए क्या मदद करूँ?" if is_hi else f"Hello {new_name}! Your account is ready. How can I assist you?"
                        st.session_state.messages = [{"role": "assistant", "content": welcome_txt}]
                        st.session_state.personal_notes = []
                        db_query("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", 
                                 (new_uname, "assistant", welcome_txt), commit=True)
                        st.success("खाता सफलतापूर्वक बन गया!" if is_hi else "Account created successfully!")
                        st.rerun()
    st.stop()

# --- 2. Main Dashboard (Logged In) ---
is_hi = (st.session_state.app_lang == "Hindi")

# Sidebar
st.sidebar.write(f"👤 **{st.session_state.logged_in_name}**")
if st.sidebar.button("लॉगआउट (Logout)" if is_hi else "Logout", use_container_width=True):
    st.session_state.logged_in_user = None
    st.session_state.logged_in_name = None
    st.session_state.messages = []
    st.session_state.personal_notes = []
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ सेटिंग्स (Settings)" if is_hi else "⚙️ Settings")

# Language Setting in Sidebar
chosen_lang = st.sidebar.selectbox("🌐 भाषा (Language):", ["हिंदी (Hindi)", "English"], index=0 if is_hi else 1)
new_lang = "Hindi" if "हिंदी" in chosen_lang else "English"
if new_lang != st.session_state.app_lang:
    st.session_state.app_lang = new_lang
    st.rerun()

bot_mode = st.sidebar.selectbox(
    "अंदाज़ (Mode):" if is_hi else "Mode:", 
    ["दोस्ताना", "शिक्षक", "कहानीकार"] if is_hi else ["Friendly", "Teacher", "Storyteller"]
)
voice_speed = st.sidebar.radio("आवाज़ की गति:" if is_hi else "Voice Speed:", ["सामान्य", "धीमी"] if is_hi else ["Normal", "Slow"])
is_slow_voice = (voice_speed in ["धीमी", "Slow"])

st.sidebar.markdown("---")
st.sidebar.subheader("📝 डायरी (Notes)" if is_hi else "📝 Notes Diary")
new_note = st.sidebar.text_input("नया काम लिखें:" if is_hi else "Add new note:", placeholder="उदा. 5 बजे काम है")
if st.sidebar.button("नोट जोड़ें" if is_hi else "Add Note", use_container_width=True):
    if new_note.strip():
        db_query("INSERT INTO notes (username, note) VALUES (?, ?)", (st.session_state.logged_in_user, new_note.strip()), commit=True)
        st.session_state.personal_notes.append(new_note.strip())
        st.sidebar.success("नोट सुरक्षित सेव हुआ!" if is_hi else "Note saved!")
        st.rerun()

if st.session_state.personal_notes:
    for idx, note in enumerate(st.session_state.personal_notes):
        st.sidebar.write(f"{idx+1}. {note}")
    if st.sidebar.button("सारे नोट हटाएँ" if is_hi else "Clear All Notes", use_container_width=True):
        db_query("DELETE FROM notes WHERE username = ?", (st.session_state.logged_in_user,), commit=True)
        st.session_state.personal_notes = []
        st.rerun()

if st.sidebar.button("पूरी चैट साफ़ करें" if is_hi else "Clear Entire Chat", use_container_width=True):
    db_query("DELETE FROM chat_history WHERE username = ?", (st.session_state.logged_in_user,), commit=True)
    welcome_text = f"नमस्ते {st.session_state.logged_in_name} जी! मैं जुगनू हूँ।" if is_hi else f"Hello {st.session_state.logged_in_name}! I am JUGNU."
    st.session_state.messages = [{"role": "assistant", "content": welcome_text}]
    db_query("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (st.session_state.logged_in_user, "assistant", welcome_text), commit=True)
    st.session_state.pop("last_voice", None)
    st.rerun()

# Creator Banner
c1, c2 = st.columns([1, 4])
with c1:
    creator_img = None
    for fname in ["creater 1.jpg", "creater 1.png", "creator 1.jpg", "creator 1.png", "creater.jpg", "creator.jpg"]:
        if os.path.exists(fname):
            creator_img = fname
            break
    if not creator_img:
        for f in os.listdir("."):
            if f.lower().endswith((".jpg", ".png", ".jpeg")):
                creator_img = f
                break
    if creator_img:
        st.image(creator_img, width=80)
    else:
        st.write("👑")

with c2:
    st.subheader("✨ JUGNU AI")
    st.caption("निर्माता: अरविंद सिंह | पर्सनल स्मार्ट साथी" if is_hi else "Created by: Arvind Singh | Personal Smart Assistant")

st.divider()

# Backend API
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

def try_evaluate_math(prompt_text, lang="Hindi"):
    text = prompt_text.lower().replace("प्रतिशत", "%").replace("percent", "%")
    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ka|का|of)\s*(\d+(?:\.\d+)?)\s*%", text)
    if pct_match:
        res = (float(pct_match.group(1)) * float(pct_match.group(2))) / 100.0
        return f"{pct_match.group(1)} का {pct_match.group(2)}% बराबर {res:g} होगा।" if lang == "Hindi" else f"{pct_match.group(2)}% of {pct_match.group(1)} is {res:g}."
    clean = text.replace("गुना", "*").replace("गुणा", "*").replace("into", "*").replace("x", "*")
    clean = clean.replace("भाग", "/").replace("divide", "/").replace("बटा", "/")
    clean = clean.replace("जोड़", "+").replace("plus", "+").replace("घटाव", "-").replace("minus", "-")
    expr_match = re.search(r"(\d+(?:\.\d+)?\s*[\+\-\*\/]\s*\d+(?:\.\d+)?)", clean)
    if expr_match:
        try:
            ans = eval(expr_match.group(1), {"__builtins__": None}, {})
            return f"उत्तर {ans:g} है।" if lang == "Hindi" else f"The answer is {ans:g}."
        except Exception:
            pass
    return None

def fetch_image_from_prompt(prompt_text):
    clean = prompt_text.lower()
    for w in ["photo", "फोटो", "तस्वीर", "tasveer", "image", "चित्र", "banao", "बनाओ", "बनाकर", "दो", "chahiye", "मुझे", "एक", "की", "का"]:
        clean = clean.replace(w, "")
    clean = clean.strip()
    if "jaisalmer" in clean or "जैसलमेर" in clean:
        query, caption = "golden majestic Jaisalmer fort Thar desert photography", "जैसलमेर फोर्ट"
    elif "bullet" in clean or "bike" in clean:
        query, caption = "Royal Enfield bullet bike parked in desert rajasthan", "रॉयल एनफील्ड बुलेट"
    elif "desert" in clean or "रेगिस्तान" in clean:
        query, caption = "beautiful Thar desert golden sand dunes rajasthan", "थार रेगिस्तान"
    else:
        query, caption = (clean if clean else "beautiful Rajasthan landscape"), (clean if clean else "सुंदर दृश्य")
    return f"https://image.pollinations.ai/prompt/{urllib.parse.quote(query)}?width=800&height=500&nologo=true", caption

def get_jugnu_response(prompt_text, mode_name, lang="Hindi"):
    p = prompt_text.lower().strip()
    
    # Image generation trigger
    if any(k in p for k in ["photo", "फोटो", "तस्वीर", "tasveer", "image", "चित्र"]) and any(a in p for a in ["banao", "बनाओ", "बनाकर", "dikhao", "generate", "create", "chahiye"]):
        img_url, cap = fetch_image_from_prompt(prompt_text)
        return f"IMAGE_GEN:{img_url}|{cap}"
        
    # Creator info
    if any(k in p for k in ["bare me", "batao", "kahan ke", "papa", "pita", "father", "village", "gaav", "who made", "creator"]) and any(w in p for w in ["jisne", "banaya", "arvind", "creator", "made you"]):
        if lang == "Hindi":
            return "मुझे अरविंद सिंह ने बनाया है और उनके पापा का नाम मिस्टर रेवंत सिंह है और उनका गाँव दूजासर है और अभी श्री मोहनगढ़ में रहते हैं।"
        return "I was created by Arvind Singh. His father is Mr. Rewant Singh, his native village is Doojasar, and he currently lives in Shri Mohangarh."
        
    if any(k in p for k in ["kisne banaya", "creator kaun", "किसने बनाया", "who created you"]):
        return "मुझे अरविंद सिंह ने बनाया है।" if lang == "Hindi" else "I was created by Arvind Singh."

    # Notes
    if any(k in p for k in ["mere note", "mere notes", "kya kaam", "meri diary", "नोट बताओ", "my notes"]):
        if not st.session_state.personal_notes:
            return "आपकी डायरी में अभी कोई नोट सेव नहीं है।" if lang == "Hindi" else "You have no notes saved yet."
        return ("आपकी डायरी के काम: " if lang == "Hindi" else "Your notes: ") + "। ".join([f"{i+1}: {n}" for i, n in enumerate(st.session_state.personal_notes)])

    # Math
    math_ans = try_evaluate_math(prompt_text, lang)
    if math_ans:
        return math_ans

    # Time & Date
    if any(k in p for k in ["samay", "time", "kitne baje", "तारीख", "date", "दिन", "समय"]):
        ist_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
        days = {"Monday": "सोमवार", "Tuesday": "मंगलवार", "Wednesday": "बुधवार", "Thursday": "गुरुवार", "Friday": "शुक्रवार", "Saturday": "शनिवार", "Sunday": "रविवार"}
        if any(k in p for k in ["samay", "time", "समय"]):
            return f"अभी समय {ist_now.strftime('%I:%M %p')} हुआ है।" if lang == "Hindi" else f"The current time is {ist_now.strftime('%I:%M %p')}."
        return f"आज {days.get(ist_now.strftime('%A'), '')} है और तारीख {ist_now.strftime('%d-%m-%Y')} है।" if lang == "Hindi" else f"Today is {ist_now.strftime('%A')}, {ist_now.strftime('%d-%m-%Y')}."

    # Groq Chat
    if lang == "Hindi":
        sys_txt = f"तुम जुगनू AI हो, जिसे अरविंद सिंह ने बनाया है। उपयोगकर्ता का नाम {st.session_state.logged_in_name} है। शुद्ध हिंदी में 1-2 छोटे वाक्यों में स्वाभाविक उत्तर दो।"
    else:
        sys_txt = f"You are JUGNU AI, created by Arvind Singh. The user's name is {st.session_state.logged_in_name}. Respond naturally in 1-2 concise English sentences."

    # Groq Supported Models fallback list
    candidate_models = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"]
    for m in candidate_models:
        try:
            res = client.chat.completions.create(
                model=m,
                messages=[{"role": "system", "content": sys_txt}, {"role": "user", "content": prompt_text}],
                max_tokens=150,
                temperature=0.4
            )
            return res.choices[0].message.content.strip()
        except Exception:
            continue
    return "माफ़ी चाहता हूँ, इस समय सर्वर से उत्तर नहीं मिल पा रहा है।" if lang == "Hindi" else "Sorry, I could not fetch a response at this moment."

# Chat Message Stream (ChatGPT Style)
total_msgs = len(st.session_state.messages)
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        c = msg["content"]
        if c.startswith("IMAGE_GEN:"):
            parts = c.replace("IMAGE_GEN:", "").split("|")
            st.write(f"🎨 **जुगनू ने बनाई: {parts[1]}**" if is_hi else f"🎨 **Generated: {parts[1]}**")
            st.image(parts[0], use_container_width=True)
            st.markdown(f"[यहाँ क्लिक करके फोटो डाउनलोड करें]({parts[0]})" if is_hi else f"[Download Photo]({parts[0]})")
        else:
            st.write(c)
            if msg["role"] == "assistant":
                play_audio(c, autoplay=(i == total_msgs - 1 and total_msgs > 1), slow=is_slow_voice, lang=st.session_state.app_lang)

# 8 Responsive Suggestion Buttons
st.write("")
st.caption("त्वरित सुझाव:" if is_hi else "Quick Suggestions:")
r1 = st.columns(4)
r2 = st.columns(4)
quick_prompt = None

if is_hi:
    if r1[0].button("👑 निर्माता", use_container_width=True): quick_prompt = "tum ko jisne banaya ha unke bare me kutch batayo"
    if r1[1].button("⏰ समय", use_container_width=True): quick_prompt = "Abhi kya samay hua hai?"
    if r1[2].button("🌤 मौसम", use_container_width=True): quick_prompt = "Mohangarh me mausam kaisa hai?"
    if r1[3].button("😄 चुटकुला", use_container_width=True): quick_prompt = "Ek mazedaar chhota chutkula sunao"

    if r2[0].button("🎨 फोटो", use_container_width=True): quick_prompt = "photo banao Jaisalmer Fort"
    if r2[1].button("🎯 क्विज़", use_container_width=True): quick_prompt = "Mujhse Rajasthan se juda samanya gyan ka sawal poocho."
    if r2[2].button("🍎 सेहत", use_container_width=True): quick_prompt = "Aaj ke liye ek health tip batao."
    if r2[3].button("📝 नोट्स", use_container_width=True): quick_prompt = "mere notes batao"
else:
    if r1[0].button("👑 Creator", use_container_width=True): quick_prompt = "Tell me about your creator."
    if r1[1].button("⏰ Time", use_container_width=True): quick_prompt = "What is the time right now?"
    if r1[2].button("🌤 Weather", use_container_width=True): quick_prompt = "How is the weather today?"
    if r1[3].button("😄 Joke", use_container_width=True): quick_prompt = "Tell me a short funny joke."

    if r2[0].button("🎨 Photo", use_container_width=True): quick_prompt = "photo banao Jaisalmer Fort"
    if r2[1].button("🎯 Quiz", use_container_width=True): quick_prompt = "Ask me a simple trivia question."
    if r2[2].button("🍎 Health", use_container_width=True): quick_prompt = "Give me one healthy lifestyle tip."
    if r2[3].button("📝 Notes", use_container_width=True): quick_prompt = "my notes"

# Centered Mic Widget
st.write("")
_, col_mic, _ = st.columns([1, 1, 1])
with col_mic:
    voice_input = st.audio_input("माइक", key="jugnu_mic_box", label_visibility="collapsed")

# User Text Input & Disclaimer
user_text = st.chat_input("यहाँ लिखकर या ऊपर माइक से पूछिए..." if is_hi else "Ask here or use the mic above...")
st.caption("जुगनू एक AI है और इससे गलतियाँ हो सकती हैं।" if is_hi else "JUGNU is an AI and may make mistakes.")

def handle_user_query(query_text):
    st.session_state.messages.append({"role": "user", "content": query_text})
    db_query("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", 
             (st.session_state.logged_in_user, "user", query_text), commit=True)
    
    with st.spinner("जुगनू काम कर रहा है..." if is_hi else "JUGNU is thinking..."):
        reply = get_jugnu_response(query_text, bot_mode, st.session_state.app_lang)
    
    q_low = query_text.lower()
    if not reply.startswith("IMAGE_GEN:"):
        if "youtube" in q_low:
            term = query_text.replace("youtube", "").replace("par", "").strip()
            reply += f"\n\n▶ [YouTube पर देखें](https://www.youtube.com/results?search_query={term})"
        elif "google" in q_low:
            term = query_text.replace("google", "").replace("par", "").strip()
            reply += f"\n\n🔍 [Google पर खोजें](https://www.google.com/search?q={term})"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    db_query("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", 
             (st.session_state.logged_in_user, "assistant", reply), commit=True)
    st.rerun()

if quick_prompt:
    handle_user_query(quick_prompt)
elif voice_input is not None:
    audio_bytes = voice_input.getvalue()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != audio_bytes):
        st.session_state.last_voice = audio_bytes
        with st.spinner("आवाज़ सुनी जा रही है..." if is_hi else "Listening..."):
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
