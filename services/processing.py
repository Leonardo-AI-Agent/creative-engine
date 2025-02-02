import asyncio
import shutil
from pathlib import Path
from fastapi import HTTPException
from loguru import logger
from gradio_client import Client, handle_file

from config import DATA_DIR, HF_MODEL, HUGGINGFACE_API_TOKEN
from utils.retry import retry_async

# Initialize Gradio client.
client = Client(HF_MODEL, hf_token=HUGGINGFACE_API_TOKEN)

async def wait_for_file(filepath: Path, retries: int = 3, delay: int = 2) -> bool:
    """
    Waits asynchronously until a file exists and is non-empty.
    """
    current_delay = delay
    for attempt in range(retries):
        if filepath.exists() and filepath.stat().st_size > 0:
            logger.info(f"✅ File found: {filepath}")
            return True
        logger.warning(f"⚠️ File {filepath} not found (Attempt {attempt+1}/{retries}) - Retrying in {current_delay}s...")
        await asyncio.sleep(current_delay)
        current_delay *= 2
    return False

async def process_3d_job(image_path: Path, timestamp: str) -> dict:
    """
    Processes an image file to produce a 3D preview (video) by:
      1. Validating the image.
      2. Starting a session and running preprocessing lambdas.
      3. Submitting the 3D conversion job and polling for the result.
    """
    if not await wait_for_file(image_path):
        raise HTTPException(status_code=400, detail=f"Image file not found: {image_path}")

    logger.info("🚀 Starting Gradio session for 3D conversion...")
    session_result = await asyncio.to_thread(client.predict, api_name="/start_session")
    logger.info(f"✅ Session started: {session_result}")

    logger.info("⚙️ Running preprocessing lambda...")
    lambda_result = await asyncio.to_thread(client.predict, api_name="/lambda")
    logger.info(f"✅ Lambda executed: {lambda_result}")

    job = client.submit(
        image=handle_file(str(image_path)),
        seed=42,
        ss_guidance_strength=7.5,
        ss_sampling_steps=12,
        slat_guidance_strength=3.0,
        slat_sampling_steps=12,
        api_name="/image_to_3d"
    )

    logger.info("⏳ Waiting for 3D conversion job result... (Max 5 min)")
    retries = 8
    delay = 10
    result = job.result(timeout=600)
    for attempt in range(retries):
        if result and "video" in result and result["video"]:
            break
        logger.warning(f"⚠️ No video found, retrying... ({attempt+1}/{retries}) in {delay}s")
        await asyncio.sleep(delay)
        delay = min(delay + 5, 80)
        result = job.result(timeout=600)
    if not result or "video" not in result or not result["video"]:
        logger.error("❌ 3D conversion failed: No video file returned.")
        raise HTTPException(status_code=500, detail="3D conversion failed: No video returned.")

    return result

async def extract_glb_async(timestamp: str) -> str:
    """
    Extracts the GLB model (and Gaussian representation) by:
      - Running a series of preprocessing lambdas.
      - Using retry logic to perform GLB extraction.
      - Downloading or copying the resulting files.
    Returns the GLB file path (as a string) or None on failure.
    """
    try:
        logger.info("🛠 Extracting GLB model...")
        for lambda_api in ["/lambda_1", "/lambda_2", "/lambda_3"]:
            lambda_result = await asyncio.to_thread(client.predict, api_name=lambda_api)
            logger.info(f"✅ {lambda_api} executed: {lambda_result}")

        glb_result = await retry_async(
            lambda mesh_simplify, texture_size, api_name: asyncio.to_thread(
                client.predict, mesh_simplify=mesh_simplify, texture_size=texture_size, api_name=api_name
            ),
            retries=3,
            initial_delay=5,
            mesh_simplify=0.95,
            texture_size=1024,
            api_name="/extract_glb"
        )
        if not glb_result:
            logger.error("❌ GLB extraction failed after multiple attempts.")
            return None

        glb_path, _ = glb_result  # Expecting a tuple: (path, extra_info)
        glb_file_path = DATA_DIR / f"{timestamp}_3d_model.glb"

        # We use a blocking file copy in a thread.
        from services.file_handler import fetch_or_copy_file
        await fetch_or_copy_file(glb_path, glb_file_path)
        logger.info(f"🗿 GLB Extracted: {glb_file_path}")

        logger.info("🔎 Extracting Gaussian representation...")
        gaussian_result = await asyncio.to_thread(client.predict, api_name="/extract_gaussian")
        gaussian_path, _ = gaussian_result
        gaussian_file_path = DATA_DIR / f"{timestamp}_gaussian.glb"
        await fetch_or_copy_file(gaussian_path, gaussian_file_path)
        logger.info(f"🌫️ Gaussian Extracted: {gaussian_file_path}")

        return str(glb_file_path)
    except Exception as e:
        logger.error(f"❌ GLB extraction failed: {e}")
        return None
