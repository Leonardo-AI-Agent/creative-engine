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
import asyncio
import json
import httpx
from loguru import logger

# Import local service functions.
from services.sketch_generator import generate_sketch  # local async function for sketches
from services.model_generator import generate_3d_preview, generate_model  # local async functions for 3D preview/model
from api_calls import stream_chat  # external API function for chat
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
    /* Hide default header, menu, and footer */
    #MainMenu, header, footer {visibility: hidden;}
    /* Custom styling for buttons */
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
    /* Loading overlay for animated pulsing effect */
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
        ["Chat", "Generate Sketch (Image)", "Generate 3D Preview", "Generate 3D Model"], index=1
    )
    # Add the Clean button with an icon (here we use a broom emoji).
    if st.button("🧹 Clean", key="clean"):
        st.session_state.messages = []
        st.session_state.last_image = None
        st.session_state.processing = False
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

def display_chat():
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])
                if msg.get("image"):
                    st.image(msg["image"], use_container_width=True)
                if msg.get("video"):
                    st.video(msg["video"])

st.title("ChatGPT Terminal with Modern UI")
display_chat()

# -------------------------------
# Fake Non-linear Progress Bar that Exits Early When File Is Ready
# -------------------------------
def run_fake_progress_until_event(event, total_time=75.0, update_interval=0.5):
    progress_bar = st.progress(0)
    message_placeholder = st.empty()
    iterations = int(total_time / update_interval)
    for i in range(iterations):
        if event.is_set():
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
# "Generate Sketch (Image)" Service
# -------------------------------
if service == "Generate Sketch (Image)":
    st.header("Generate Sketch (Image)")
    prompt_text = st.text_input("Enter your prompt", placeholder="A beautiful landscape")
    style_option = st.selectbox(
        "Choose style (optional)",
        ["", "Realistic", "Low Poly", "Voxel", "Stylized", "Toon", "Sci-Fi", "Fantasy", "Wireframe", "Clay", "Metallic"],
        index=5  # Default to "Toon"
    )
    if st.button("Generate Image", key="generate_sketch", disabled=st.session_state.processing):
        if prompt_text:
            st.session_state.processing = True
            st.session_state.last_image = None
            thread_results = {}
            file_ready_event = threading.Event()
            # Create an image placeholder for animated loading preview.
            image_placeholder = st.empty()
            loading_gif_url = "https://media.giphy.com/media/3oEjI6SIIHBdRxXI40/giphy.gif"
            image_placeholder.image(loading_gif_url, use_container_width=True)
            def call_generate_sketch():
                try:
                    image_filepath = asyncio.run(generate_sketch(prompt_text, style_option))
                    thread_results["image_filepath"] = image_filepath
                except Exception as e:
                    thread_results["error"] = str(e)
                finally:
                    file_ready_event.set()
            thread = threading.Thread(target=call_generate_sketch)
            thread.start()
            run_fake_progress_until_event(file_ready_event, total_time=75.0, update_interval=0.5)
            thread.join()
            st.session_state.processing = False
            if "error" in thread_results:
                st.error(f"Error generating image: {thread_results['error']}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error generating image: {thread_results['error']}"
                })
            elif "image_filepath" in thread_results:
                st.session_state.last_image = thread_results["image_filepath"]
                image_placeholder.image(st.session_state.last_image, width=300, caption="Generated Sketch", use_container_width=True)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Here is your generated image:",
                    "image": st.session_state.last_image
                })
        else:
            st.error("Please enter a prompt.")

# -------------------------------
# "Generate 3D Preview" Service using Local Service Functions
# -------------------------------
elif service == "Generate 3D Preview":
    st.header("Generate 3D Preview (Video)")
    uploaded_file = st.file_uploader("Upload an image file", type=["png", "jpg", "jpeg"])
    if uploaded_file and st.button("Generate 3D Preview"):
        # Create a preview container with an animated loading overlay.
        try:
            file_bytes = uploaded_file.getvalue()
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
        file_ready_event = threading.Event()
        def call_generate_preview():
            try:
                result = asyncio.run(generate_3d_preview(uploaded_file))
                thread_results.update(result)
            except Exception as e:
                thread_results["error"] = str(e)
            finally:
                file_ready_event.set()
        thread = threading.Thread(target=call_generate_preview)
        thread.start()
        run_fake_progress_until_event(file_ready_event, total_time=75.0, update_interval=0.5)
        thread.join()
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
            st.markdown(f'<video src="{video_path}" autoplay controls style="width: 100%;"></video>', unsafe_allow_html=True)
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Here is your 3D preview video:" + (f"\nSubtitles: {subtitles}" if subtitles else ""),
                "video": video_path
            })

# -------------------------------
# "Generate 3D Model" Service using Local Service Functions
# -------------------------------
elif service == "Generate 3D Model":
    st.header("Generate 3D Model")
    uploaded_file = st.file_uploader("Upload an image file", type=["png", "jpg", "jpeg"])
    if uploaded_file and st.button("Generate 3D Model"):
        try:
            glb_filepath = asyncio.run(generate_model(uploaded_file))
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"3D model generated: {glb_filepath}"
            })
        except Exception as e:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"Error generating 3D model: {str(e)}"
            })

# -------------------------------
# "Chat" Service using External API (stream_chat)
# -------------------------------
elif service == "Chat":
    st.header("Chat")
    prompt = st.chat_input("Ask your question:")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        temp_loader = {"role": "assistant", "content": "Streaming response..."}
        st.session_state.messages.append(temp_loader)
        display_chat()  # Show current chat (user + loader)
        stream_placeholder = st.empty()  # For live updates
        final_response = ""
        logger.info(f"Calling stream_chat with prompt: {prompt} and user_id: {st.session_state.user_id}")
        try:
            for chunk in stream_chat(prompt, st.session_state.user_id, CHAT_BASE_URL):
                final_response += chunk
                stream_placeholder.markdown(final_response)
                time.sleep(0.001)
            logger.info(f"Completed chat streaming. Final response length: {len(final_response)} characters")
        except Exception as e:
            logger.exception("Exception during chat stream")
            final_response = f"Streaming error: {str(e)}"
            stream_placeholder.markdown(final_response)
        stream_placeholder.empty()
        if st.session_state.messages and st.session_state.messages[-1] == temp_loader:
            st.session_state.messages.pop()
        st.session_state.messages.append({"role": "assistant", "content": final_response})
        display_chat()
else:
    if prompt := st.chat_input("What do you want to see..."):
        st.session_state.messages.append({"role": "assistant", "content": f"Echo: {prompt}"})

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
                glb_filepath = asyncio.run(generate_model(upload_file))
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
                result = asyncio.run(generate_3d_preview(upload_file))
                video_path = result["video_filepath"]
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
