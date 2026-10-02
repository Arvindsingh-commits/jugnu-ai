import os
import io
import re
import urllib.parse
import datetime
from io import BytesIO
import streamlit as st
import requests
from groq import Groq
from gtts import gTTS

st.set_page_config(page_title="JUGNU AI", page_icon="✨", layout="centered")
st.markdown("", unsafe_allow_html=True)

# --- Session States ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]
if "personal_notes" not in st.session_state:
    st.session_state.personal_notes = []

# --- Sidebar: Settings & Tools ---
st.sidebar.title("✨ JUGNU Settings")

bot_mode = st.sidebar.selectbox(
    "JUGNU का अंदाज़ (Mode):",
    ["दोस्ताना (Friendly)", "शिक्षक (Study / Teacher)", "कहानीकार (Storyteller)"]
)

voice_speed_option = st.sidebar.radio(
    "आवाज़ की गति (Voice Speed):",
    ["सामान्य (Normal)", "धीमी (Slow)"],
    index=0
)
is_slow_voice = (voice_speed_option == "धीमी (Slow)")

st.sidebar.markdown("---")
st.sidebar.subheader("📝 जुगनू डायरी (Notes)")
new_note = st.sidebar.text_input("नया काम लिखें:", key="input_new_note", placeholder="उदा. 5 बजे बैंक जाना है")
if st.sidebar.button("➕ नोट जोड़ें", use_container_width=True):
    if new_note.strip():
        st.session_state.personal_notes.append(new_note.strip())
        st.sidebar.success("नोट सेव हो गया!")
        st.rerun()

if st.session_state.personal_notes:
    st.sidebar.write("**आपके काम:**")
    for idx, note in enumerate(st.session_state.personal_notes):
        st.sidebar.markdown(f"{idx+1}. {note}")
    if st.sidebar.button("🗑️ सारे नोट साफ़ करें", use_container_width=True):
        st.session_state.personal_notes = []
        st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ पूरी चैट साफ़ करें", use_container_width=True):
    st.session_state.messages = [
        {"role": "assistant", "content": "नमस्ते! मैं जुगनू हूँ। कहिए आज मैं आपकी क्या मदद कर सकता हूँ?"}
    ]
    st.session_state.pop("last_voice", None)
    st.rerun()

# --- Creator Profile Banner ---
col1, col2 = st.columns([1, 4])
with col1:
    creator_img = None
    check_list = [
        "creater 1.jpg", "creater 1.png", "creater 1.jpeg", "creater 1.webp",
        "creater1.jpg", "creater1.png", "creater1.jpeg",
        "creater.jpg", "creater.png", "creater.jpeg",
        "creator 1.jpg", "creator 1.png", "creator 1.jpeg", "creator 1.webp",
        "creator1.jpg", "creator1.png", "creator1.jpeg",
        "creator.jpg", "creator.png", "creator.jpeg"
    ]
    for fname in check_list:
        if os.path.exists(fname):
            creator_img = fname
            break
            
    if not creator_img:
        for f in os.listdir("."):
            lower_f = f.lower()
            if any(lower_f.endswith(ext) for ext in [".jpg", ".png", ".jpeg", ".webp"]):
                creator_img = f
                break

    if creator_img:
        st.image(creator_img, width=95)
    else:
        st.markdown("### 👑")

with col2:
    st.markdown("### ✨ JUGNU AI Assistant")
    st.caption("निर्माता: **अरविंद सिंह** | आपका पर्सनल स्मार्ट साथी")

st.divider()

# --- Groq Client Setup ---
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def play_audio(text, autoplay=False, slow=False):
    try:
        clean_text = text.split("```")[0].strip()
        clean_text = clean_text.split("http")[0].split("▶️")[0].split("🔍")[0].strip()
        if not clean_text or clean_text.startswith("IMAGE_GEN:"):
            return
        clean_text = clean_text[:250]
        
        sound = BytesIO()
        tts = gTTS(text=clean_text, lang="hi", slow=slow)
        tts.write_to_fp(sound)
        sound.seek(0)
        
        st.audio(sound, format="audio/mp3", autoplay=autoplay)
    except Exception:
        pass

def try_evaluate_math(prompt_text):
    text = prompt_text.lower().replace("प्रतिशत", "%").replace("percent", "%")
    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ka|का|of)\s*(\d+(?:\.\d+)?)\s*%", text)
    if not pct_match:
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:of|ka|का)?\s*(\d+(?:\.\d+)?)", text)
        if pct_match:
            pct_val = float(pct_match.group(1))
            num_val = float(pct_match.group(2))
            res = (num_val * pct_val) / 100.0
            return f"{num_val} का {pct_val}% बराबर {res:g} होगा।"
    else:
        num_val = float(pct_match.group(1))
        pct_val = float(pct_match.group(2))
        res = (num_val * pct_val) / 100.0
        return f"{num_val} का {pct_val}% बराबर {res:g} होगा।"

    clean = text.replace("गुना", "*").replace("गुणा", "*").replace("into", "*").replace("x", "*")
    clean = clean.replace("भाग", "/").replace("divide", "/").replace("बटा", "/")
    clean = clean.replace("जोड़", "+").replace("plus", "+").replace("धन", "+")
    clean = clean.replace("घटाव", "-").replace("minus", "-").replace("ऋण", "-")
    
    expr_match = re.search(r"(\d+(?:\.\d+)?\s*[\+\-\*\/]\s*\d+(?:\.\d+)?)", clean)
    if expr_match:
        try:
            expr = expr_match.group(1)
            ans = eval(expr, {"__builtins__": None}, {})
            return f"हिसाब के अनुसार उत्तर {ans:g} है।"
        except Exception:
            pass
    return None

def fetch_image_from_prompt(prompt_text):
    clean = prompt_text.lower()
    for w in ["photo", "फोटो", "तस्वीर", "tasveer", "image", "चित्र", "banao", "बनाओ", "बनाकर", "दो", "chahiye", "मुझे", "एक", "की", "का"]:
        clean = clean.replace(w, "")
    clean = clean.strip()
    
    # Prompt translation / enhancement
    if "jaisalmer" in clean or "जैसलमेर" in clean:
        query = "majestic golden Jaisalmer fort in the Thar desert rajasthan high quality photography"
        caption = "जैसलमेर का किला (Jaisalmer Fort)"
    elif "bullet" in clean or "bike" in clean:
        query = "Royal Enfield bullet motorcycle parked near desert dunes 4k"
        caption = "रॉयल एनफील्ड बुलेट"
    elif "desert" in clean or "रेगिस्तान" in clean:
        query = "beautiful Thar desert golden sand dunes rajasthan sunset"
        caption = "थार रेगिस्तान"
    else:
        query = clean if clean else "beautiful palace in Rajasthan India 4k"
        caption = clean if clean else "सुंदर राजस्थान"

    encoded = urllib.parse.quote(query)
    image_url = f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){encoded}?width=800&height=500&nologo=true&seed=42"
    return image_url, caption

def get_jugnu_response(prompt_text, mode_name):
    p = prompt_text.lower().strip()

    # Image Generation Check
    image_keywords = ["photo", "फोटो", "तस्वीर", "tasveer", "image", "चित्र"]
    action_keywords = ["banao", "बनाओ", "बनाकर", "banakar", "dikhao", "दिखाओ", "generate", "create", "चाहिए"]
    if any(k in p for k in image_keywords) and any(a in p for a in action_keywords):
        img_url, cap = fetch_image_from_prompt(prompt_text)
        return f"IMAGE_GEN:{img_url}|{cap}"

    # Creator Details
    creator_keywords = [
        "bare me", "bare mein", "batao", "btao", "kutch batayo", "kuch batao",
        "kahan ke", "kahan rahte", "papa", "pita", "father", "village", "gaav", "gaon"
    ]
    if any(k in p for k in creator_keywords) and any(w in p for w in ["jisne", "jisne banaya", "banaya", "uske", "unke", "arvind", "creator", "nirmata"]):
        return "मुझे अरविंद सिंह ने बनाया है और उनके पापा का नाम मिस्टर रेवंत सिंह है और उनका गाँव दूजासर है और अभी श्री मोहनगढ़ में रहते हैं।"

    if any(k in p for k in ["kisne banaya", "kisne bnaya", "tumko kisne", "creator kaun", "creator kon", "किसने बनाया"]):
        return "मुझे अरविंद सिंह ने बनाया है।"

    # Notes
    if any(k in p for k in ["mere note", "mere notes", "kya kaam", "meri diary", "mera note", "नोट बताओ"]):
        if not st.session_state.personal_notes:
            return "आपकी डायरी में अभी कोई नोट सेव नहीं है। आप साइडबार में नया नोट जोड़ सकते हैं।"
        notes_str = "। ".join([f"{i+1}: {nt}" for i, nt in enumerate(st.session_state.personal_notes)])
        return f"आपकी डायरी में ये काम लिखे हैं: {notes_str}।"

    # Math
    math_ans = try_evaluate_math(prompt_text)
    if math_ans:
        return math_ans

    # Live Time & Date
    if any(k in p for k in ["samay", "time", "kitne baje", "kya samay", "तारीख", "date", "दिन", "din", "समय"]):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        ist_now = now_utc + datetime.timedelta(hours=5, minutes=30)
        time_str = ist_now.strftime("%I:%M %p")
        date_str = ist_now.strftime("%d-%m-%Y")
        
        days_hindi = {
            "Monday": "सोमवार", "Tuesday": "मंगलवार", "Wednesday": "बुधवार",
            "Thursday": "गुरुवार", "Friday": "शुक्रवार", "Saturday": "शनिवार", "Sunday": "रविवार"
        }
        day_en = ist_now.strftime("%A")
        day_hi = days_hindi.get(day_en, day_en)

        if any(k in p for k in ["samay", "time", "kitne baje", "समय"]):
            return f"अभी समय {time_str} हुआ है।"
        return f"आज {day_hi} है और तारीख {date_str} है।"

    # Weather
    if any(k in p for k in ["mausam", "weather", "taapman", "tapman", "मौसम"]):
        if any(w in p for w in ["mohangarh", "mohan garh", "मोहनगढ़"]):
            return "श्री मोहनगढ़ में मौसम धूप भरा और सुहावना है। दिन में हल्की गर्माहट और हवा चल रही है।"
        return "आज का मौसम साफ़ और सामान्य बना हुआ है।"

    # LLM Chat
    mode_instructions = "तुम बहुत दोस्ताना और मददगार स्वभाव में बात करो।"
    if "शिक्षक" in mode_name:
        mode_instructions = "तुम एक बुद्धिमान शिक्षक की तरह ज्ञानवर्धक, सटीक और स्पष्ट भाषा में समझाओ।"
    elif "कहानीकार" in mode_name:
        mode_instructions = "तुम एक कहानीकार की तरह बहुत रोचक, मधुर और मनमोहक अंदाज़ में उत्तर दो।"

    system_prompt = (
        f"तुम जुगनू (JUGNU) हो, अरविंद सिंह द्वारा बनाए गए एक समझदार हिंदी AI सहायक। "
        f"{mode_instructions} "
        "तुम्हारा उत्तर केवल और केवल शुद्ध हिंदी (Devanagari script) में होना चाहिए। "
        "उत्तर 1 या 2 छोटे वाक्यों में स्वाभाविक तरीके से दो।"
    )

    try:
        models_data = client.models.list().data
        active_ids = [m.id for m in models_data]
        usable_models = [
            m for m in active_ids 
            if not any(bad in m.lower() for bad in ["whisper", "guard", "moderation", "vision"])
        ]
    except Exception as e:
        return f"Groq Error: {str(e)}"

    last_error = ""
    for model_name in usable_models:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=150,
                temperature=0.4
            )
            reply = completion.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as err:
            last_error = str(err)
            continue

    return f"Error: {last_error}" if last_error else "माफ़ कीजिए, कोई सक्रिय मॉडल नहीं मिला।"

# Display Chat History
total_msgs = len(st.session_state.messages)
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        content = msg["content"]
        if content.startswith("IMAGE_GEN:"):
            parts = content.replace("IMAGE_GEN:", "").split("|")
            img_url = parts[0]
            cap = parts[1] if len(parts) > 1 else "AI Photo"
            
            # Fetch directly from backend so it loads immediately on screen
            try:
                img_data = requests.get(img_url, timeout=15).content
                st.image(img_data, caption=f"🎨 जुगनू ने बनाई: {cap}", use_container_width=True)
            except Exception:
                st.markdown(f"🎨 **{cap}**")
                st.markdown(f"[![फोटो लोड हो रही है]({img_url})]({img_url})")

            st.markdown(f"📥 [यहाँ क्लिक करके फ़ोटो डाउनलोड करें]({img_url})")
        else:
            st.markdown(content)
            if msg["role"] == "assistant":
                play_audio(content, autoplay=(i == total_msgs - 1 and total_msgs > 1), slow=is_slow_voice)

# Sidebar Chat Export
chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
st.sidebar.download_button(
    label="📥 बातचीत डाउनलोड करें",
    data=chat_text,
    file_name="jugnu_chat_history.txt",
    mime="text/plain",
    use_container_width=True
)

# Quick Suggestion Buttons
st.write("")
st.markdown("💡 **त्वरित सवाल (Quick Tap):**")
q_row1 = st.columns(4)
q_row2 = st.columns(4)
quick_prompt = None

if q_row1[0].button("👑 निर्माता कौन है?", use_container_width=True):
    quick_prompt = "tum ko jisne banaya ha unke bare me kutch batayo"
if q_row1[1].button("⏰ अभी क्या समय है?", use_container_width=True):
    quick_prompt = "Abhi kya samay hua hai?"
if q_row1[2].button("🎨 फोटो बनाओ", use_container_width=True):
    quick_prompt = "photo banao Jaisalmer Fort"
if q_row1[3].button("😄 एक चुटकुला", use_container_width=True):
    quick_prompt = "Ek mazedaar chhota chutkula sunao"

if q_row2[0].button("🎯 क्विज़ खेलें", use_container_width=True):
    quick_prompt = "Mujhse Rajasthan ya Bharat se juda ek rochak samanya gyan ka sawal poocho jisme 4 vikalp hon."
if q_row2[1].button("🍎 सेहत टिप", use_container_width=True):
    quick_prompt = "Aaj ke liye ek chhota aur faydemand health tip batao."
if q_row2[2].button("📝 मेरे नोट्स", use_container_width=True):
    quick_prompt = "mere notes batao"
if q_row2[3].button("📖 एक सुविचार", use_container_width=True):
    quick_prompt = "Aaj ka achha suvichar batao"

with st.container(border=True):
    st.markdown("🎙 **JUGNU से बोलकर पूछने के लिए नीचे रिकॉर्ड करें:**")
    voice_input = st.audio_input("Record audio", key="jugnu_mic", label_visibility="collapsed")

user_text = st.chat_input("यहाँ लिखकर पूछिए या फोटो बनाने को कहिए...")

def handle_user_query(query_text):
    st.session_state.messages.append({"role": "user", "content": query_text})
    with st.spinner("जुगनू काम कर रहा है..."):
        reply = get_jugnu_response(query_text, bot_mode)
    
    q_low = query_text.lower()
    if not reply.startswith("IMAGE_GEN:"):
        if "youtube" in q_low:
            search_term = query_text.replace("youtube", "").replace("par", "").replace("khojo", "").strip()
            reply += f"\n\n▶️️ [यहाँ क्लिक करके YouTube पर देखें](https://www.youtube.com/results?search_query={search_term})"
        elif "google" in q_low:
            search_term = query_text.replace("google", "").replace("par", "").replace("khojo", "").strip()
            reply += f"\n\n🔍 [यहाँ क्लिक करके Google पर खोजें](https://www.google.com/search?q={search_term})"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()

if quick_prompt:
    handle_user_query(quick_prompt)
elif voice_input is not None:
    audio_bytes = voice_input.getvalue()
    if ("last_voice" not in st.session_state) or (st.session_state.last_voice != audio_bytes):
        st.session_state.last_voice = audio_bytes
        with st.spinner("आपकी आवाज़ सुनी जा रही है..."):
            recognized_text = ""
            try:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "recording.wav"
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3-turbo",
                    language="hi"
                )
                recognized_text = transcription.text.strip()
            except Exception as e:
                st.error(f"Voice error: {str(e)}")

        if recognized_text:
            handle_user_query(f"🎙 {recognized_text}")
elif user_text:
    handle_user_query(user_text)
