import sys
import os
import base64
import io
from starlette.datastructures import UploadFile

# Add the parent directory so that config.py, api_calls.py, and services are found.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import time
import threading
import uuid
from loguru import logger
from api_calls import stream_chat
from ui.helpers import display_chat, run_progress
from ui.service_handlers import (
    handle_generate_sketch,
    handle_generate_3d_preview,
    handle_generate_3d_model,
    handle_chat,
)
from config import CHAT_BASE_URL

# -------------------------------
# Page Configuration & CSS
# -------------------------------
st.set_page_config(
    page_title="LEONAI TERMINAL",
    page_icon=":robot_face:",
    layout="wide",
)

st.markdown(
    """
    <style>
    #MainMenu, header, footer {visibility: hidden;}
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
    .loading-overlay {
       position: absolute;
       top: 50%;
       left: 50%;
       transform: translate(-50%, -50%);
       width: 100px;
       height: 100px;
       background: url('https://media.giphy.com/media/3oEjI6SIIHBdRxXI40/giphy.gif') no-repeat center center;
       background-size: contain;
       opacity: 0.8;
       animation: pulse 1s infinite;
    }
    @keyframes pulse {
       0% { opacity: 0.5; }
       50% { opacity: 1; }
       100% { opacity: 0.5; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------
# Sidebar: Instructions, Service Selection & Clean Button
# -------------------------------
with st.sidebar:
    st.header("Instructions")
    st.markdown(
        """
        This demo shows a LEONAI terminal with:
          - 3D assets, Images, Videos.
        **Select a service:**
          - Chat
          - Generate Sketch (Image)
          - Generate 3D Preview
          - Generate 3D Model
        """
    )
    service = st.selectbox(
        "Select Service",
        ["Chat", "Generate Sketch (Image)", "Generate 3D Preview", "Generate 3D Model"]
    )
    if st.button("🧹 Clean", key="clean"):
        st.session_state.messages = []
        st.session_state.last_image = None
        st.session_state.processing = False
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
    st.info("Built with modern Streamlit components and minimalistic design.")

# -------------------------------
# Session State Initialization
# -------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_image" not in st.session_state:
    st.session_state.last_image = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

def update_display():
    st.title("LEONAI TERMINAL DEMO")
    display_chat(st.session_state.messages)

update_display()

# -------------------------------
# Service Branches
# -------------------------------
if service == "Generate Sketch (Image)":
    st.header("Generate Sketch (Image)")
    prompt_text = st.text_input("Enter your prompt", placeholder="A beautiful landscape")
    style_option = st.selectbox(
        "Choose style (optional)",
        ["", "Realistic", "Low Poly", "Voxel", "Stylized", "Toon", "Sci-Fi", "Fantasy", "Wireframe", "Clay", "Metallic"],
        index=5
    )
    if st.button("Generate Image", key="generate_sketch", disabled=st.session_state.processing):
        if prompt_text:
            st.session_state.processing = True
            st.session_state.last_image = None
            thread_results = {}
            event = threading.Event()
            def call_sketch():
                thread, evt, res = handle_generate_sketch(prompt_text, style_option)
                thread.join()
                thread_results.update(res)
                evt.set()
            t = threading.Thread(target=call_sketch)
            t.start()
            run_progress(event, total_time=75.0, update_interval=0.5)
            t.join()
            st.session_state.processing = False
            if "error" in thread_results:
                st.error(f"Error generating image: {thread_results['error']}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error generating image: {thread_results['error']}"
                })
            elif "image_filepath" in thread_results:
                st.session_state.last_image = thread_results["image_filepath"]
                st.image(st.session_state.last_image, width=300, caption="Generated Sketch", use_container_width=True)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Here is your generated image:",
                    "image": st.session_state.last_image
                })
        else:
            st.error("Please enter a prompt.")

elif service == "Generate 3D Preview":
    st.header("Generate 3D Preview (Video)")
    # Use last generated sketch if available; otherwise, allow file upload.
    if st.session_state.last_image:
        st.info("Using the last generated sketch for 3D Preview.")
        with open(st.session_state.last_image, "rb") as f:
            file_bytes = f.read()
        upload_file = UploadFile(filename=os.path.basename(st.session_state.last_image), file=io.BytesIO(file_bytes))
    else:
        upload_file = st.file_uploader("Upload an image file", type=["png", "jpg", "jpeg"])
    if upload_file and st.button("Generate 3D Preview"):
        try:
            file_bytes = upload_file.getvalue()
            encoded_image = base64.b64encode(file_bytes).decode("utf-8")
            preview_placeholder = st.empty()
            preview_html = f"""
            <div style="position: relative; display: inline-block; width: 100%;">
                <img src="data:image/png;base64,{encoded_image}" style="width: 100%;" />
                <div class="loading-overlay"></div>
            </div>
            """
            preview_placeholder.markdown(preview_html, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error processing image preview: {str(e)}")
        
        thread_results = {}
        event = threading.Event()
        def call_preview():
            res = handle_generate_3d_preview(upload_file)
            thread_results.update(res)
            event.set()
        t = threading.Thread(target=call_preview)
        t.start()
        run_progress(event, total_time=75.0, update_interval=0.5)
        t.join()
        if "error" in thread_results:
            st.error(f"Error generating 3D preview: {thread_results['error']}")
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"Error generating 3D preview: {thread_results['error']}"
            })
        elif "video_filepath" in thread_results:
            video_path = thread_results["video_filepath"]
            subtitles = thread_results.get("subtitles", "")
            preview_placeholder.empty()
            try:
                with open(video_path, "rb") as vf:
                    video_bytes = vf.read()
                encoded_video = base64.b64encode(video_bytes).decode("utf-8")
                st.markdown(
                    f'<video src="data:video/mp4;base64,{encoded_video}" autoplay controls style="width: 100%;"></video>',
                    unsafe_allow_html=True
                )
            except Exception as e:
                st.error(f"Error displaying video: {str(e)}")
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Here is your 3D preview video:" + (f"\nSubtitles: {subtitles}" if subtitles else ""),
                "video": video_path
            })

elif service == "Generate 3D Model":
    st.header("Generate 3D Model")
    if st.session_state.last_image:
        st.info("Using the last generated sketch for 3D Model.")
        with open(st.session_state.last_image, "rb") as f:
            file_bytes = f.read()
        upload_file = UploadFile(filename=os.path.basename(st.session_state.last_image), file=io.BytesIO(file_bytes))
    else:
        upload_file = st.file_uploader("Upload an image file", type=["png", "jpg", "jpeg"])
    if upload_file and st.button("Generate 3D Model"):
        try:
            res = handle_generate_3d_model(upload_file)
            if "error" in res:
                raise Exception(res["error"])
            glb_filepath = res.get("glb_filepath")
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"3D model generated: {glb_filepath}"
            })
        except Exception as e:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"Error generating 3D model: {str(e)}"
            })

elif service == "Chat":
    st.header("Chat")
    # Use a key so that the chat input value is stored in session state.
    prompt = st.chat_input("Ask your question:", key="chat_input")
    if prompt:
        # Append the user's prompt only if it's new
        if st.session_state.get("last_chat_prompt") != prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.last_chat_prompt = prompt
            logger.info("Chat: Appended new user prompt: '{}'", prompt)
        else:
            logger.info("Chat: Prompt '{}' already processed.", prompt)
        
        # Append a temporary loader message.
        temp_loader = {"role": "assistant", "content": "Streaming response..."}
        st.session_state.messages.append(temp_loader)
        logger.debug("Chat: Appended temporary loader message.")
        
        # Display the current chat (user prompt + loader).
        display_chat(st.session_state.messages)
        
        logger.info("Chat: Calling handle_chat with prompt '{}' and user_id '{}'", prompt, st.session_state.user_id)
        # Call the dedicated chat handler.
        result = handle_chat(prompt, st.session_state.user_id, CHAT_BASE_URL)
        
        if "error" in result:
            final_response = f"Streaming error: {result['error']}"
            logger.error("Chat: Error from handle_chat: {}", result["error"])
        else:
            final_response = result["response"]
            logger.info("Chat: Final response received (length: {})", len(final_response))
        
        # Replace the temporary loader with the final response.
        if st.session_state.messages and st.session_state.messages[-1]["content"] == "Streaming response...":
            st.session_state.messages[-1] = {"role": "assistant", "content": final_response}
            logger.info("Chat: Replaced temporary loader with final response.")
        else:
            st.session_state.messages.append({"role": "assistant", "content": final_response})
            logger.info("Chat: Appended final response to session state.")
        
        # Display the updated chat.
        display_chat(st.session_state.messages)


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
                img_path = st.session_state.last_image
                logger.info(f"Processing image for 3D model: {img_path}")
                with open(img_path, "rb") as f:
                    file_bytes = f.read()
                upload_file = UploadFile(filename=os.path.basename(img_path), file=io.BytesIO(file_bytes))
                res = handle_generate_3d_model(upload_file)
                if "error" in res:
                    raise Exception(res["error"])
                glb_filepath = res.get("glb_filepath")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"3D model generated: {glb_filepath}"
                })
            except Exception as e:
                logger.exception("Exception during 3D model generation from sketch")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Request error: {str(e)}"
                })
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="preview-btn">', unsafe_allow_html=True)
        if st.button("Generate 3D Preview", key="preview_button"):
            try:
                img_path = st.session_state.last_image
                logger.info(f"Processing image for 3D preview: {img_path}")
                with open(img_path, "rb") as f:
                    file_bytes = f.read()
                upload_file = UploadFile(filename=os.path.basename(img_path), file=io.BytesIO(file_bytes))
                result = handle_generate_3d_preview(upload_file)
                if "error" in result:
                    raise Exception(result["error"])
                video_path = result.get("video_filepath")
                subtitles = result.get("subtitles", "")
                content = "Here is your 3D preview video."
                if subtitles:
                    content += f"\nSubtitles: {subtitles}"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": content,
                    "video": video_path
                })
            except Exception as e:
                logger.exception("Exception during 3D preview generation from sketch")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Request error: {str(e)}"
                })
        st.markdown('</div>', unsafe_allow_html=True)
