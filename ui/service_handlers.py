import streamlit as st
import time
import threading
import asyncio
from loguru import logger
import httpx

# Import local service functions from your services.
from services.sketch_generator import generate_sketch
from services.model_generator import generate_3d_preview, generate_model
from api_calls import stream_chat  # stream_chat still calls an external API

def handle_sketch_generation(prompt_text, style_option):
    """Handles sketch generation service. Returns a tuple (error, image_filepath)."""
    thread_results = {}
    file_ready_event = threading.Event()
    
    def call_generate_sketch():
        try:
            # Call the local async generate_sketch without BASE_URL.
            image_filepath = asyncio.run(generate_sketch(prompt_text, style_option))
            thread_results["image_filepath"] = image_filepath
        except Exception as e:
            thread_results["error"] = str(e)
        finally:
            file_ready_event.set()
    
    thread = threading.Thread(target=call_generate_sketch)
    thread.start()
    return thread, file_ready_event, thread_results

def handle_chat(prompt, user_id):
    """Handles the Chat service using stream_chat.
       Returns the final response string."""
    final_response = ""
    try:
        for chunk in stream_chat(prompt, user_id):
            final_response += chunk
            # Optionally, you could update a placeholder here.
            time.sleep(0.001)
        logger.info(f"Completed chat streaming. Final response length: {len(final_response)} characters")
    except Exception as e:
        logger.exception("Exception during chat stream")
        final_response = f"Streaming error: {str(e)}"
    return final_response

def handle_3d_preview(file_data):
    """Handles the 3D Preview service using the local async function.
       Returns a tuple (video_path, subtitles)."""
    # Assuming generate_3d_preview is asynchronous.
    return asyncio.run(generate_3d_preview(file_data))

def handle_3d_model(file_data):
    """Handles the 3D Model service using the local async function.
       Returns the glb_filepath."""
    return asyncio.run(generate_model(file_data))
