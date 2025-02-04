# api_calls.py
import requests
import time
import httpx
from loguru import logger

def generate_sketch(prompt: str, style: str, base_url: str) -> str:
    """
    Sends a request to generate a sketch image.
    Returns the image filepath on success.
    """
    payload = {"prompt": prompt, "style": style if style else None}
    start_time = time.time()
    response = requests.post(f"{base_url}/generate_sketch", json=payload)
    elapsed = time.time() - start_time
    logger.info(f"/generate_sketch processing time: {elapsed:.2f} seconds")
    if response.status_code == 200:
        image_filepath = response.json().get("image_filepath")
        logger.info(f"Received image filepath: {image_filepath}")
        return image_filepath
    else:
        raise Exception(f"Error generating image: {response.text}")

def generate_3d_preview(file_data: bytes, base_url: str) -> (str, str):
    """
    Sends a request to generate a 3D preview video.
    Returns a tuple: (video_filepath, subtitles).
    """
    start_time = time.time()
    files = {"file": file_data}
    response = requests.post(f"{base_url}/generate_3d_preview", files=files)
    elapsed = time.time() - start_time
    logger.info(f"/generate_3d_preview processing time: {elapsed:.2f} seconds")
    if response.status_code == 200:
        result = response.json()
        return result.get("video_filepath"), result.get("subtitles")
    else:
        raise Exception(f"Error generating 3D preview: {response.text}")

def generate_3d_model(file_data: bytes, base_url: str) -> str:
    """
    Sends a request to generate a 3D model.
    Returns the GLB file path on success.
    """
    start_time = time.time()
    files = {"file": file_data}
    response = requests.post(f"{base_url}/generate_model", files=files)
    elapsed = time.time() - start_time
    logger.info(f"/generate_model processing time: {elapsed:.2f} seconds")
    if response.status_code == 200:
        return response.json().get("glb_filepath")
    else:
        raise Exception(f"Error generating 3D model: {response.text}")

def stream_chat(question: str, user_id: str, chat_base_url: str):
    """
    Streams the answer from the chat endpoint, yielding each chunk.
    """
    payload = {"question": question, "user_id": user_id}
    with httpx.Client(timeout=None) as client:
        with client.stream("POST", f"{chat_base_url}/query/stream", json=payload) as response:
            for chunk in response.iter_text():
                yield chunk
