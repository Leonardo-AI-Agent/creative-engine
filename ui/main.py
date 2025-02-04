import streamlit as st
import streamlit.components.v1 as components

# -------------------------------
# Page Configuration & Custom CSS
# -------------------------------
st.set_page_config(
    page_title="ChatGPT Terminal",
    page_icon=":robot_face:",
    layout="wide",
)

# Custom Glassmorphism CSS for Chat Input
st.markdown(
    """
    <style>
    /* Hide the default Streamlit header, menu, and footer */
    #MainMenu, header, footer {visibility: hidden;}

    /* Position the chat input container at the bottom */
    .stChatInputContainer {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        width: 80%;
        max-width: 600px;
        z-index: 1000;
    }

    /* Glassmorphism styling for the input field */
    .stChatInputContainer textarea {
        background: rgba(255, 255, 255, 0.08) !important;
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 20px;
        padding: 14px 18px;
        color: rgba(255, 255, 255, 0.9) !important;
        font-size: 16px;
        width: 100%;
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.15);
        transition: all 0.3s ease-in-out;
    }

    /* Placeholder text */
    .stChatInputContainer textarea::placeholder {
        color: rgba(255, 255, 255, 0.5);
    }

    /* Hover effect */
    .stChatInputContainer textarea:hover {
        background: rgba(255, 255, 255, 0.12) !important;
        box-shadow: 0px 6px 18px rgba(0, 0, 0, 0.2);
    }

    /* Focus effect */
    .stChatInputContainer textarea:focus {
        background: rgba(255, 255, 255, 0.2) !important;
        border: 1px solid rgba(255, 255, 255, 0.3);
        outline: none;
    }

    /* Send button styling */
    .stChatInputContainer button {
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(15px);
        border-radius: 50%;
        padding: 12px;
        border: none;
        box-shadow: 0px 3px 10px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease-in-out;
    }

    /* Send button hover */
    .stChatInputContainer button:hover {
        background: rgba(255, 255, 255, 0.2);
        box-shadow: 0px 6px 18px rgba(0, 0, 0, 0.25);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------
# Sidebar: Instructions & About
# -------------------------------
with st.sidebar:
    st.header("Instructions")
    st.markdown(
        """
        This demo shows a ChatGPT‐like terminal with:
        - **3D assets**
        - **Images**
        - **Videos**
        
        **Try typing**:
        - `3d` for a 3D asset
        - `image` for an image
        - `video` for a video
        """
    )
    st.info("Built with modern Streamlit components and minimalistic design.")

# -------------------------------
# Session State: Conversation History
# -------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# -------------------------------
# Function to Display Chat History
# -------------------------------
def display_chat():
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])
                if msg.get("image"):
                    st.image(msg["image"], use_column_width=True)
                if msg.get("video"):
                    st.video(msg["video"])

# -------------------------------
# Main Chat Container
# -------------------------------
st.title("ChatGPT Terminal with Glassmorphism UI")

# Display the conversation history
display_chat()

# -------------------------------
# Chat Input with Glassmorphism
# -------------------------------
if prompt := st.chat_input("What do you want to see..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate a response (dummy response for now)
    response = {"text": f"Echo: {prompt}"}
    st.session_state.messages.append({"role": "assistant", "content": response["text"]})

    # Rerun the app to update the chat
    st.experimental_rerun()
