import os, io, re, base64, sqlite3, urllib.parse, datetime
from io import BytesIO
from PIL import Image
import streamlit as st
from groq import Groq
from gtts import gTTS
from pypdf import PdfReader
from duckduckgo_search import DDGS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")

# --- Database ---
DB_FILE = "jugnu_data.db"
def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(query, params)
    res = cur.fetchone() if fetchone else (cur.fetchall() if fetchall else None)
    if commit: conn.commit()
    conn.close()
    return res

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, name TEXT, plan_type TEXT DEFAULT 'free')")
c.execute("CREATE TABLE IF NOT EXISTS conversations (session_id TEXT PRIMARY KEY, username TEXT, title TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS user_memories (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, fact TEXT)")
c.execute("INSERT OR IGNORE INTO users VALUES ('arvind', 'अरविंद सिंह', 'vip')")
conn.commit()
conn.close()

# --- States & Persistent Login ---
q_user = st.query_params.get("user", "arvind")
st.query_params["user"] = q_user
st.session_state.setdefault("logged_in_user", q_user)
st.session_state.setdefault("logged_in_name", "अरविंद सिंह")
st.session_state.setdefault("user_plan", "vip")
st.session_state.setdefault("current_session_id", datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
st.session_state.setdefault("messages", [{"role": "assistant", "content": "राम राम अरविंद सिंह जी! मैं जुगनू हूँ। हुकम करो, आज कांई सेवा करूँ?"}])
st.session_state.setdefault("call_mode", False)
st.session_state.setdefault("doc_text", "")
st.session_state.setdefault("img_b64", None)

# --- Sidebar ---
st.sidebar.write(f"👤 **{st.session_state.logged_in_name}** (👑 VIP PRO)")
c1, c2 = st.sidebar.columns(2)
if c1.button("➕ नई चैट", use_container_width=True):
    st.session_state.current_session_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    st.session_state.messages = [{"role": "assistant", "content": "राम राम सा! नई चैट तैयार है।"}]
    st.session_state.doc_text, st.session_state.img_b64 = "", None
    st.rerun()
if c2.button("🚪 रीसेट", use_container_width=True):
    st.session_state.messages = []
    st.rerun()

st.sidebar.markdown("---")

# 1. Voice Call Button
call_txt = "🔴 कॉल काटें (End Call)" if st.session_state.call_mode else "📞 वॉयस कॉल मोड चालू करें"
if st.sidebar.button(call_txt, use_container_width=True):
    st.session_state.call_mode = not st.session_state.call_mode
    st.rerun()

# 2. Kamayi & VIP Dashboard
with st.sidebar.expander("💰 कमाई व VIP डैशबोर्ड", expanded=False):
    users = db_query("SELECT username, name, plan_type FROM users", fetchall=True)
    for u in (users or []):
        st.write(f"• **{u[1]}** (`{u[0]}`) — {u[2].upper()}")
    sel_u = st.selectbox("यूज़र:", [u[0] for u in (users or [])], key="u_sel")
    sel_p = st.radio("प्लान:", ["free", "vip"], horizontal=True, key="p_sel")
    if st.button("सेव करें", use_container_width=True):
        db_query("UPDATE users SET plan_type=? WHERE username=?", (sel_p, sel_u), commit=True)
        st.success("प्लान अपडेट!")
        st.rerun()

# 3. Memory
with st.sidebar.expander("🧠 याददाश्त (Memory)", expanded=False):
    m_in = st.text_input("याद रखने की बात:")
    if st.button("याद रखो", use_container_width=True) and m_in:
        db_query("INSERT INTO user_memories (username, fact) VALUES (?,?)", (st.session_state.logged_in_user, m_in.strip()), commit=True)
        st.success("याद रख लिया!")
        st.rerun()
    mems = db_query("SELECT fact FROM user_memories WHERE username=?", (st.session_state.logged_in_user,), fetchall=True)
    for m in (mems or []): st.write(f"• {m[0]}")

bot_mode = st.sidebar.selectbox("अंदाज़:", ["मारवाड़ी / राजस्थानी", "दोस्ताना", "शिक्षक", "कहानीकार"])

# --- Main UI Header ---
st.subheader("✨ JUGNU AI (सुपर AI)")
st.caption("निर्माता: अरविंद सिंह | पर्सनल स्मार्ट साथी")
st.divider()

if st.session_state.call_mode:
    st.info("📞 **लाइव वॉयस कॉल एक्टिव है!** माइक दबाकर बोलें, जुगनू सीधे आवाज़ में जवाब देगा।")

client = Groq(api_key=st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY"))

def speak(txt, auto=False):
    try:
        clean = txt.split("http")[0].replace("IMAGE_GEN:", "").strip()
        if not clean or clean.startswith("त्रुटि:"): return
        s = BytesIO()
        gTTS(text=clean[:250], lang="hi").write_to_fp(s)
        s.seek(0)
        st.audio(s, format="audio/mp3", autoplay=auto)
    except: pass

def get_reply(prompt):
    p = prompt.lower().strip()
    if any(k in p for k in ["kisne banaya", "किसने बनाया"]):
        return "मुझे अरविंद सिंह ने बनाया है, जिनका गाँव दूजासर है और वर्तमान में श्री मोहनगढ़ में रहते हैं।"
    if any(k in p for k in ["marwadi", "मारवाड़ी"]) and any(k in p for k in ["bol", "aati", "sakte"]):
        return "हाँ भाई, म्हूँ मीठी मारवाड़ी बोल सकूँ हूँ! हुकम करो, आज कांई बात करनी है?"
    if any(k in p for k in ["photo", "फोटो"]) and any(a in p for a in ["banao", "बनाओ"]):
        q = urllib.parse.quote(prompt.replace("photo","").replace("फोटो","").replace("banao","").strip() or "Rajasthan fort")
        return f"IMAGE_GEN:https://image.pollinations.ai/prompt/{q}?width=800&height=500&nologo=true|{prompt}"
    
    sys_msg = f"तुम जुगनू AI हो, जिसे अरविंद सिंह ने बनाया है। यूजर {st.session_state.logged_in_name} हैं।"
    if "मारवाड़ी" in bot_mode or "marwadi" in p:
        sys_msg += " शुद्ध मीठी मारवाड़ी/राजस्थानी में 1-2 छोटे वाक्यों में स्वाभाविक व आदर से जवाब दो।"
    else:
        sys_msg += " शुद्ध हिंदी में 1-2 छोटे वाक्यों में सटीक व मददगार जवाब दो।"
        
    mems = db_query("SELECT fact FROM user_memories WHERE username=?", (st.session_state.logged_in_user,), fetchall=True)
    if mems: sys_msg += "\nयाददाश्त: " + "; ".join([m[0] for m in mems])
    if st.session_state.doc_text: sys_msg += f"\nफ़ाइल डेटा: {st.session_state.doc_text}"

    for model_name in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
                max_tokens=180, temperature=0.4
            )
            return res.choices[0].message.content.strip()
        except Exception: continue
    return "माफ़ी चाहता हूँ, कृपया 2 सेकंड बाद दोबारा पूछें।"

# Messages
total = len(st.session_state.messages)
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        if m["content"].startswith("IMAGE_GEN:"):
            url, name = m["content"].replace("IMAGE_GEN:", "").split("|")
            st.image(url, caption=name)
        else:
            st.write(m["content"])
            if m["role"] == "assistant":
                speak(m["content"], auto=(st.session_state.call_mode or (i == total - 1 and total > 1)))

# Quick Buttons
r1, r2, r3, r4 = st.columns(4)
q_ask = None
if r1.button("👑 निर्माता", use_container_width=True): q_ask = "kisne banaya"
if r2.button("😄 चुटकुला", use_container_width=True): q_ask = "Ek mast chhota chutkula sunao"
if r3.button("🎨 फोटो", use_container_width=True): q_ask = "photo banao Jaisalmer desert"
if r4.button("💬 मारवाड़ी", use_container_width=True): q_ask = "kya tum marwadi bol sakti ho"

# Mic
_, cm, _ = st.columns([1,1,1])
with cm: v_in = st.audio_input("माइक", key="mic", label_visibility="collapsed")

# File Upload
with st.expander("📎 फ़ाइल या फ़ोटो जोड़ें", expanded=False):
    up = st.file_uploader("फ़ाइल चुनें:", type=["pdf", "txt", "png", "jpg"], key="f_up")
    if up:
        if up.name.endswith(".pdf"):
            st.session_state.doc_text = "\n".join([p.extract_text() or "" for p in PdfReader(up).pages])[:3000]
            st.success("PDF जुड़ गई!")
        elif up.name.endswith(".txt"):
            st.session_state.doc_text = up.read().decode("utf-8")[:3000]
            st.success("फ़ाइल जुड़ गई!")
        else:
            st.image(up, width=150)
            st.success("फ़ोटो जुड़ गई!")

u_text = st.chat_input("यहाँ लिखकर, ऊपर माइक से या 📎 फ़ाइल जोड़कर पूछिए...")

def handle_msg(text):
    s_id = st.session_state.current_session_id
    st.session_state.messages.append({"role": "user", "content": text})
    db_query("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (s_id, "user", text), commit=True)
    with st.spinner("जुगनू..."):
        ans = get_reply(text)
    st.session_state.messages.append({"role": "assistant", "content": ans})
    db_query("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (s_id, "assistant", ans), commit=True)
    st.rerun()

if q_ask: handle_msg(q_ask)
elif v_in is not None:
    ab = v_in.getvalue()
    if st.session_state.get("last_v") != ab:
        st.session_state.last_v = ab
        try:
            aud = io.BytesIO(ab); aud.name = "r.wav"
            tr = client.audio.transcriptions.create(file=aud, model="whisper-large-v3-turbo", language="hi")
            if tr.text.strip(): handle_msg(f"🎙 {tr.text.strip()}")
        except: pass
elif u_text: handle_msg(u_text)
