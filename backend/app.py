import asyncio
import streamlit as st
from mcp_client import run_agent

st.set_page_config(page_title="Ethereum Assistant", page_icon="🪙")

st.title("Ethereum Assistant")
st.caption("Chat mit deinem Agenten-Team")

# Chat-Historie im Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Bisherige Nachrichten anzeigen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Eingabefeld unten
if prompt := st.chat_input("Frag mich etwas!"):
    # Nutzer-Nachricht speichern + anzeigen
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Agent-Antwort holen
    with st.chat_message("assistant"):
        with st.spinner("Agenten-Team denkt nach ..."):
            # run_agent ist async → einmal synchron ausführen
            response_text = asyncio.run(run_agent(prompt))

            st.markdown(response_text)

    # Antwort in der Historie speichern
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )