import asyncio
import streamlit as st
from mcp_client import run_agent
import uuid

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Ethereum Assistant", page_icon="֍")

# -----------------------------
# Lightweight custom styling (CSS)
# -----------------------------
st.markdown(
    """
<style>
    /* Limit width for better readability and center content a bit */
    .block-container {
        max-width: 850px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* Slightly rounded buttons with smooth hover effect */
    .stButton > button {
        border-radius: 10px;
        padding: 0.45rem 0.9rem;
        border: none;
        transition: 0.2s;
    }

    .stButton > button:hover {
        filter: brightness(1.15);
        transform: translateY(-1px);
    }

    /* Nicer alert boxes (info, warning, error) */
    .stAlert {
        border-radius: 10px !important;
        padding: 1rem !important;
    }

    /* Slight padding for chat messages */
    .stChatMessage {
        border-radius: 10px !important;
        padding: 0.75rem !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Sidebar with quick actions
# -----------------------------
quick_prompt = None  # will store sidebar button selection

with st.sidebar:
    st.header("⚡ Schnellaktionen")

    if st.button("Was ist Ethereum?"):
        quick_prompt = "Was ist Ethereum?"

    if st.button("ETH/CHF Kurs"):
        quick_prompt = "Wie viel ist 1 ETH in CHF wert?"

    if st.button("Was ist eine DAO?"):
        quick_prompt = "Erkläre mir eine DAO."

    st.markdown("---")

    st.header("🔐 Hinweis")
    st.write(
        """
Dieser Assistant ist ein Prototyp für eine Bachelorarbeit.
Bitte triff keine finanziellen Entscheidungen nur aufgrund dieser Antworten.
        """
    )

# -----------------------------
# Main title and caption
# -----------------------------
st.title("֍ Ethereum Assistant")
st.caption("Interagiere in natürlicher Sprache mit der Blockchain.")

# -----------------------------
# Initialize chat history
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# -----------------------------
# Display previous messages
# -----------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Show hint when no chat exists yet
if len(st.session_state.messages) == 0:
    st.info(
        "👋 Willkommen! Du kannst Fragen zu Ethereum, Smart Contracts oder DAOs stellen. "
        "Die wichtigsten Schnellaktionen findest du links in der Seitenleiste."
    )

# -----------------------------
# Chat input
# -----------------------------
user_input = st.chat_input("Frag mich etwas!")

# Decide which input to use: user input or quick action from sidebar
prompt_to_use = user_input or quick_prompt

# -----------------------------
# Process agent interaction
# -----------------------------
if prompt_to_use:
    # Store and display user message
    st.session_state.messages.append({"role": "user", "content": prompt_to_use})
    with st.chat_message("user"):
        st
