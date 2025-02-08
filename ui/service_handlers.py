import asyncio
import threading
import json
from loguru import logger
from services.sketch_generator import generate_sketch
from services.model_generator import generate_3d_preview, generate_model
from api_calls import stream_chat

def handle_generate_sketch(prompt, style):
    """
    Calls the local async generate_sketch() and returns a tuple:
      (thread, event, results)
    where results is a dict containing "image_filepath" on success or "error".
    """
    results = {}
    event = threading.Event()
    def task():
        try:
            filepath = asyncio.run(generate_sketch(prompt, style))
            results["image_filepath"] = filepath
            logger.info("handle_generate_sketch: Successfully generated sketch at {}", filepath)
        except Exception as e:
            results["error"] = str(e)
            logger.exception("handle_generate_sketch: Exception while generating sketch")
        finally:
            event.set()
    thread = threading.Thread(target=task)
    thread.start()
    return thread, event, results

def handle_generate_3d_preview(upload_file):
    """
    Calls the local async generate_3d_preview() with the provided UploadFile.
    Returns the result dict (should contain "video_filepath" and optionally "subtitles").
    """
    try:
        result = asyncio.run(generate_3d_preview(upload_file))
        logger.info("handle_generate_3d_preview: Received result {}", result)
        return result
    except Exception as e:
        logger.exception("handle_generate_3d_preview: Exception while generating 3D preview")
        return {"error": str(e)}

def handle_generate_3d_model(upload_file):
    """
    Calls the local async generate_model() with the provided UploadFile.
    Returns a dict with "glb_filepath" on success.
    """
    try:
        glb_filepath = asyncio.run(generate_model(upload_file))
        logger.info("handle_generate_3d_model: Successfully generated 3D model at {}", glb_filepath)
        return {"glb_filepath": glb_filepath}
    except Exception as e:
        logger.exception("handle_generate_3d_model: Exception while generating 3D model")
        return {"error": str(e)}

def sanitize_chat_response(response_text: str) -> str:
    """
    Given the raw response text (expected to be JSON),
    this function extracts and returns only the content from the "restyle_response".
    """
    try:
        parsed = json.loads(response_text)
        # Look for the dictionary containing the "restyle_response" key.
        for item in parsed:
            if "restyle_response" in item:
                messages = item["restyle_response"].get("messages", [])
                if messages and "content" in messages[0]:
                    sanitized = messages[0]["content"]
                    logger.info("sanitize_chat_response: Extracted sanitized response: {}", sanitized)
                    return sanitized
        logger.warning("sanitize_chat_response: 'restyle_response' not found; returning full response")
        return response_text
    except Exception as e:
        logger.exception("sanitize_chat_response: Exception during sanitization")
        return response_text

def handle_chat(prompt, user_id, chat_base_url):
    """
    Calls the external stream_chat() function (from api_calls) and collects
    the streamed response. The final response is sanitized so that only the
    "restyle_response" content is returned.
    Returns a dict with either {"response": final_response} or {"error": error_msg}.
    """
    final_response = ""
    try:
        logger.info("handle_chat: Starting stream_chat for prompt '{}' and user_id '{}'", prompt, user_id)
        for chunk in stream_chat(prompt, user_id, chat_base_url):
            logger.debug("handle_chat: Received chunk: {}", chunk)
            final_response += chunk
        logger.info("handle_chat: Completed streaming; raw response length: {}", len(final_response))
        sanitized = sanitize_chat_response(final_response)
        return {"response": sanitized}
    except Exception as e:
        return {"error": str(e)}
