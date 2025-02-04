import sys
import os

# Add the parent directory to sys.path so that config.py and api_calls.py can be imported.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import time
import threading
import uuid
import httpx
import json
from loguru import logger
from api_calls import generate_sketch, generate_3d_preview, generate_3d_model, stream_chat
from config import BASE_URL, CHAT_BASE_URL


# -------------------------------
# Page Configuration & Custom CSS
# -------------------------------
st.set_page_config(
    page_title="ChatGPT Terminal",
    page_icon=":robot_face:",
    layout="wide",
)

st.markdown(
    """
    <style>
    /* Hide the default Streamlit header, menu, and footer */
    #MainMenu, header, footer {visibility: hidden;}

    /* Custom styling for additional buttons */
    .model-btn button {
       background-color: #4CAF50 !important;
       color: white !important;
       border-radius: 5px;
       transition: background-color 0.3s ease;
    }
    .model-btn button:hover {
       background-color: #45a049 !important;
    }
    .preview-btn button {
       background-color: #008CBA !important;
       color: white !important;
       border-radius: 5px;
       transition: background-color 0.3s ease;
    }
    .preview-btn button:hover {
       background-color: #007bb5 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------
# Sidebar: Instructions, Service Selection & About
# -------------------------------
with st.sidebar:
    st.header("Instructions")
    st.markdown(
        """
        This demo shows a ChatGPT‐like terminal with:
        - **3D assets**
        - **Images**
        - **Videos**

        **Select a service** from the dropdown below:
        - **Chat:** Interact via chat with streaming responses.
        - **Generate Sketch (Image):** Provide a text prompt (optionally with a style) to generate an image.
        - **Generate 3D Preview:** Upload an image to generate a 3D preview (video).
        - **Generate 3D Model:** Upload an image to generate a 3D model.
        """
    )
    service = st.selectbox(
        "Select Service", 
        ["Chat", "Generate Sketch (Image)", "Generate 3D Preview", "Generate 3D Model"]
    )
    st.info("Built with modern Streamlit components and minimalistic design.")

# -------------------------------
# Session State: Conversation History, Last Generated Sketch, Processing Flag, and User ID
# -------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_image" not in st.session_state:
    st.session_state.last_image = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

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

st.title("ChatGPT Terminal with Modern UI")
display_chat()

# -------------------------------
# Fake Non-linear Progress Bar with Dynamic Messages (for Sketch generation)
# -------------------------------
def run_fake_progress(total_time=75.0, update_interval=0.5):
    progress_bar = st.progress(0)
    message_placeholder = st.empty()
    iterations = int(total_time / update_interval)
    for i in range(iterations):
        if st.session_state.last_image is not None:
            progress_bar.progress(100)
            message_placeholder.markdown("**Done!**")
            return
        t = i * update_interval
        fraction = 1 - (1 - t / total_time) ** 3
        percent = min(int(fraction * 100), 99)
        progress_bar.progress(percent)
        if percent < 20:
            message = "Start: Making magic"
        elif percent < 40:
            message = "Concept art happening in the background."
        elif percent < 60:
            message = "Involving top artists on this design"
        elif percent < 70:
            message = "Adding some lights"
        elif percent < 90:
            message = "Nearly finished, it's looking amazing"
        else:
            message = "Get ready, you're gonna like this!"
        message_placeholder.markdown(f"**{message}**")
        time.sleep(update_interval)
    progress_bar.progress(100)
    message_placeholder.markdown("**Done!**")

# -------------------------------
# "Generate Sketch (Image)" Service with Fake Progress Bar and Button Disable
# -------------------------------
if service == "Generate Sketch (Image)":
    st.header("Generate Sketch (Image)")
    prompt_text = st.text_input("Enter your prompt", placeholder="A beautiful landscape")
    style_option = st.selectbox(
        "Choose style (optional)", 
        ["", "Realistic", "Low Poly", "Voxel", "Stylized", "Toon", "Sci-Fi", "Fantasy", "Wireframe", "Clay", "Metallic"]
    )
    if st.button("Generate Image", key="generate_sketch", disabled=st.session_state.processing):
        if prompt_text:
            st.session_state.processing = True
            st.session_state.last_image = None
            def call_generate_sketch():
                try:
                    image_filepath = generate_sketch(prompt_text, style_option, BASE_URL)
                    st.session_state.last_image = image_filepath
                except Exception as e:
                    st.session_state.messages.append({"role": "assistant", "content": f"Error generating image: {str(e)}"})
                st.session_state.processing = False
            thread = threading.Thread(target=call_generate_sketch)
            add_script_run_ctx(thread)
            thread.start()
            run_fake_progress(total_time=75.0, update_interval=0.5)
            if st.session_state.last_image:
                st.image(st.session_state.last_image, width=300, caption="Generated Sketch")
                st.session_state.messages.append({"role": "assistant", "content": "Here is your generated image:", "image": st.session_state.last_image})
        else:
            st.error("Please enter a prompt.")

# -------------------------------
# "Generate 3D Preview" Service
# -------------------------------
elif service == "Generate 3D Preview":
    st.header("Generate 3D Preview (Video)")
    uploaded_file = st.file_uploader("Upload an image file", type=["png", "jpg", "jpeg"])
    if uploaded_file and st.button("Generate 3D Preview"):
        try:
            video_path, subtitles = generate_3d_preview(uploaded_file.getvalue(), BASE_URL)
            st.session_state.messages.append({"role": "assistant", "content": "Here is your 3D preview video:", "video": video_path})
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"Error generating 3D preview: {str(e)}"})

# -------------------------------
# "Generate 3D Model" Service
# -------------------------------
elif service == "Generate 3D Model":
    st.header("Generate 3D Model")
    uploaded_file = st.file_uploader("Upload an image file", type=["png", "jpg", "jpeg"])
    if uploaded_file and st.button("Generate 3D Model"):
        try:
            glb_filepath = generate_3d_model(uploaded_file.getvalue(), BASE_URL)
            st.session_state.messages.append({"role": "assistant", "content": f"3D model generated: {glb_filepath}"})
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"Error generating 3D model: {str(e)}"})

# -------------------------------
# "Chat" Service with Streaming Response (using port 8020)
# -------------------------------
elif service == "Chat":
    # st.header("Chat")
    prompt = st.chat_input("Ask your question:")
    if prompt:
        # Append the user's prompt once.
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Add a robot message with an initial loader text in the same chat block.
        robot_msg = {"role": "assistant", "content": "Streaming response..."}
        st.session_state.messages.append(robot_msg)
        display_chat()  # Refresh the chat so far
        stream_placeholder = st.empty()  # Placeholder to update robot message in place
        answer = ""
        payload = {"question": prompt, "user_id": st.session_state.user_id}
        logger.info(f"Sending chat stream request with payload: {payload}")
        with st.spinner("Loading"):
            try:
                with httpx.Client(timeout=None) as client:
                    with client.stream("POST", f"{CHAT_BASE_URL}/query/stream", json=payload) as response:
                        logger.info("Connected to chat stream endpoint.")
                        for chunk in response.iter_text():
                            logger.debug(f"Received chunk: {chunk[:50]}...")
                            # Stream the response (append chunk as it arrives)
                            answer += chunk
                            stream_placeholder.markdown(answer)
                            time.sleep(0.001)
                logger.info(f"Completed chat streaming. Full response: {answer[:100]}...")
            except Exception as e:
                logger.exception("Exception during chat stream")
                answer = f"Streaming error: {str(e)}"
                stream_placeholder.markdown(answer)
        stream_placeholder.empty()
        # Process the JSON response to extract only the desired content.
        try:
            parsed = json.loads(answer)
            final_content = answer  # fallback
            if isinstance(parsed, list) and len(parsed) >= 2:
                restyle = parsed[1].get("restyle_response", {})
                messages_list = restyle.get("messages", [])
                if messages_list and "content" in messages_list[0]:
                    final_content = messages_list[0]["content"]
            logger.info(f"Extracted final content: {final_content[:100]}...")
        except Exception as e:
            logger.exception("Error parsing chat response")
            final_content = answer
        # Update the robot message in place.
        robot_msg["content"] = final_content
        display_chat()  # Refresh the chat display

else:
    if prompt := st.chat_input("What do you want to see..."):
        # st.session_state.messages.append({"role": "user", "content": prompt})
        response_text = f"Echo: {prompt}"
        st.session_state.messages.append({"role": "assistant", "content": response_text})

# -------------------------------
# Additional Buttons for Further Processing (if Sketch is available)
# -------------------------------
if service == "Generate Sketch (Image)" and st.session_state.last_image:
    st.markdown("### Further Processing Options")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="model-btn">', unsafe_allow_html=True)
        if st.button("Generate 3D Model", key="model_button"):
            try:
                img_url = st.session_state.last_image
                logger.info(f"Fetching image for 3D model: {img_url}")
                img_response = requests.get(img_url)
                files = {"file": img_response.content}
                response = requests.post(f"{BASE_URL}/generate_model", files=files)
                if response.status_code == 200:
                    glb_filepath = response.json().get("glb_filepath")
                    st.session_state.messages.append({"role": "assistant", "content": f"3D model generated: {glb_filepath}"})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": f"Error generating 3D model: {response.text}"})
            except Exception as e:
                logger.exception("Exception during 3D model generation from sketch")
                st.session_state.messages.append({"role": "assistant", "content": f"Request error: {str(e)}"})
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="preview-btn">', unsafe_allow_html=True)
        if st.button("Generate 3D Preview", key="preview_button"):
            try:
                img_url = st.session_state.last_image
                logger.info(f"Fetching image for 3D preview: {img_url}")
                img_response = requests.get(img_url)
                files = {"file": img_response.content}
                response = requests.post(f"{BASE_URL}/generate_3d_preview", files=files)
                if response.status_code == 200:
                    result = response.json()
                    video_path = result.get("video_filepath")
                    subtitles = result.get("subtitles")
                    content = "Here is your 3D preview video."
                    if subtitles:
                        content += f"\nSubtitles: {subtitles}"
                    st.session_state.messages.append({"role": "assistant", "content": content, "video": video_path})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": f"Error generating 3D preview: {response.text}"})
            except Exception as e:
                logger.exception("Exception during 3D preview generation from sketch")
                st.session_state.messages.append({"role": "assistant", "content": f"Request error: {str(e)}"})
        st.markdown('</div>', unsafe_allow_html=True)
