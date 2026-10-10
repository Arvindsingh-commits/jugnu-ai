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
