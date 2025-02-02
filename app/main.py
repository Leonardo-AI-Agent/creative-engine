import os
import asyncio
import httpx
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from gradio_client import Client, handle_file
from loguru import logger
from typing import Optional

# Define the request model (only one definition) with an optional style.
class PromptRequest(BaseModel):
    prompt: str
    style: Optional[str] = None

# Load environment variables
load_dotenv()

# Fetch Hugging Face API token from .env
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
if not HUGGINGFACE_API_TOKEN:
    raise ValueError("Hugging Face API token is not set in the .env file.")

# Initialize FastAPI app
app = FastAPI()

# Hugging Face private space/model
HF_MODEL = "whiteyhat/Flux-TRELLIS"

# Initialize Hugging Face Client with authentication
client = Client(HF_MODEL, hf_token=HUGGINGFACE_API_TOKEN)

# Async HTTP client for Hugging Face API requests
http_client = httpx.AsyncClient(timeout=120.0)

# Ensure the data directory exists
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# -------------------------
# Helper Functions
# -------------------------
async def download_file(url: str, local_path: Path):
    """Downloads a file asynchronously and saves it locally."""
    try:
        async with http_client.stream("GET", url) as response:
            response.raise_for_status()
            with open(local_path, "wb") as file:
                async for chunk in response.aiter_bytes():
                    file.write(chunk)
        logger.info(f"✅ File downloaded: {local_path}")
    except httpx.HTTPError as e:
        logger.error(f"❌ Download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download file.")

async def wait_for_file(filepath: Path, retries=3, delay=2):
    """Waits for a file to exist before processing it."""
    for attempt in range(retries):
        if filepath.exists() and filepath.stat().st_size > 0:
            logger.info(f"✅ File found: {filepath}")
            return True
        logger.warning(f"⚠️ File {filepath} not found (Attempt {attempt+1}/{retries}) - Retrying in {delay}s...")
        await asyncio.sleep(delay)
        delay *= 2  # Exponential backoff
    return False

async def process_3d_job(image_path: Path, timestamp: str):
    """
    Handles common 3D conversion steps:
      1. Validates the uploaded file.
      2. Starts a session and runs a preprocessing lambda.
      3. Submits the /image_to_3d job and waits (with retries) for a video result.
    Returns the job result dictionary.
    """
    if not await wait_for_file(image_path):
        raise HTTPException(status_code=400, detail=f"Image file not found: {image_path}")

    logger.info("🚀 Starting Gradio session for 3D conversion...")
    session_result = client.predict(api_name="/start_session")
    logger.info(f"✅ Session started: {session_result}")

    logger.info("⚙️ Running preprocessing lambda...")
    lambda_result = client.predict(api_name="/lambda")
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

async def extract_glb_async(timestamp: str):
    """
    Extracts the GLB model (and, as in the original code, also the Gaussian representation)
    by running several lambda calls and then downloading the GLB file.
    """
    try:
        logger.info("🛠 Extracting GLB model...")

        # Run pre-processing lambdas
        logger.info("⚙️ Running lambda_1 preprocessing...")
        lambda_1_result = client.predict(api_name="/lambda_1")
        logger.info(f"✅ Lambda_1 executed: {lambda_1_result}")

        logger.info("⚙️ Running lambda_2 preprocessing...")
        lambda_2_result = client.predict(api_name="/lambda_2")
        logger.info(f"✅ Lambda_2 executed: {lambda_2_result}")

        logger.info("⚙️ Running lambda_3 preprocessing...")
        lambda_3_result = client.predict(api_name="/lambda_3")
        logger.info(f"✅ Lambda_3 executed: {lambda_3_result}")

        # Extract the GLB model
        retries = 3
        delay = 5
        glb_result = None

        for attempt in range(retries):
            try:
                glb_result = client.predict(
                    mesh_simplify=0.95,
                    texture_size=1024,
                    api_name="/extract_glb"
                )
                if glb_result:
                    break  # exit on a valid result
            except Exception as e:
                logger.warning(f"⚠️ GLB extraction failed (Attempt {attempt+1}/{retries}). Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= 2  # exponential backoff

        if not glb_result:
            logger.error("❌ GLB extraction failed after multiple attempts.")
            return None

        glb_path, _ = glb_result  # Use the returned path
        glb_file_path = DATA_DIR / f"{timestamp}_3d_model.glb"
        if glb_path.startswith("http://") or glb_path.startswith("https://"):
            await download_file(glb_path, glb_file_path)
        else:
            shutil.copy(glb_path, glb_file_path)

        logger.info(f"🗿 GLB Extracted: {glb_file_path}")

        # Also extract Gaussian representation (functionality preserved from original code)
        logger.info("🔎 Extracting Gaussian representation...")
        gaussian_result = client.predict(api_name="/extract_gaussian")
        gaussian_path, _ = gaussian_result
        gaussian_file_path = DATA_DIR / f"{timestamp}_gaussian.glb"
        if gaussian_path.startswith("http://") or gaussian_path.startswith("https://"):
            await download_file(gaussian_path, gaussian_file_path)
        else:
            shutil.copy(gaussian_path, gaussian_file_path)
        logger.info(f"🌫️ Gaussian Extracted: {gaussian_file_path}")

        return str(glb_file_path)
    except Exception as e:
        logger.error(f"❌ GLB extraction failed: {e}")
        return None

# -------------------------
# Endpoints
# -------------------------
@app.post("/generate_sketch")
async def generate_sketch(request: PromptRequest):
    """
    Generates an image (sketch) from a text prompt with an optional style.
    If a style is provided, its descriptive text is added to the prompt.
    Then, the generated image has its background removed via an external service.
    Returns the local file path of the final image.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Map available styles to their descriptive texts.
        style_descriptions = {
            "Realistic": "Detailed textures, lifelike materials.",
            "Low Poly": "Simple shapes, flat colors.",
            "Voxel": "Blocky, pixel-style (Minecraft look).",
            "Stylized": "Hand-painted, cartoonish, vibrant.",
            "Toon": "Bold outlines, cel-shaded.",
            "Sci-Fi": "Futuristic, metallic, glowing.",
            "Fantasy": "Medieval, magical, ornate.",
            "Wireframe": "Raw mesh, technical look.",
            "Clay": "Matte, sculpted, no textures.",
            "Metallic": "Chrome, gold, shiny surfaces."
        }
        
        # Update the prompt if a valid style is provided.
        updated_prompt = request.prompt
        if request.style:
            if request.style in style_descriptions:
                updated_prompt = f"{request.prompt}. {style_descriptions[request.style]}"
            else:
                logger.warning(f"Style '{request.style}' not recognized. Using original prompt.")

        logger.info(f"🖼️ Generating flux image for prompt: {updated_prompt}")

        async def generate_image():
            return client.predict(
                prompt=updated_prompt,
                seed=42,
                randomize_seed=True,
                width=1024,
                height=1024,
                guidance_scale=3.5,
                api_name="/generate_flux_image"
            )

        image_result = await generate_image()
        image_local_path = DATA_DIR / f"{timestamp}_flux_image.png"

        # Save the generated flux image.
        if image_result.startswith("http://") or image_result.startswith("https://"):
            await download_file(image_result, image_local_path)
        else:
            shutil.copy(image_result, image_local_path)

        logger.info(f"🎨 Image saved: {image_local_path}")

        # ---------------------------------------------------------------------
        # Remove the background from the generated image using the background
        # removal service from the "not-lain/background-removal" model.
        # ---------------------------------------------------------------------
        from gradio_client import Client as GradioClient, handle_file
        bg_client = GradioClient("not-lain/background-removal")
        bg_result = bg_client.predict(
            image=handle_file(str(image_local_path)),
            api_name="/image"
        )
        # If the result is a list, take the first element.
        if isinstance(bg_result, list):
            bg_result = bg_result[0]

        image_bg_local_path = DATA_DIR / f"{timestamp}_flux_image_bg.png"
        if isinstance(bg_result, str) and (bg_result.startswith("http://") or bg_result.startswith("https://")):
            await download_file(bg_result, image_bg_local_path)
        else:
            shutil.copy(bg_result, image_bg_local_path)
        logger.info(f"🖼️ Background removed image saved: {image_bg_local_path}")

        return {"image_filepath": str(image_bg_local_path)}
    except Exception as e:
        logger.error(f"Unexpected error in generate_sketch: {e}")
        raise HTTPException(status_code=500, detail="Error generating image.")

@app.post("/generate_3d_preview")
async def generate_3d_preview(file: UploadFile = File(...)):
    """
    Accepts an image file upload and generates a 3D preview (video).
    Returns the video file path and any subtitles.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_location = DATA_DIR / f"{timestamp}_uploaded.png"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"📂 Uploaded file saved: {file_location}")

        # Process the 3D job to generate video preview
        result = await process_3d_job(file_location, timestamp)
        video_url = result["video"]
        subtitles = result.get("subtitles", None)
        video_path = DATA_DIR / f"{timestamp}_3d_preview.mp4"

        if video_url.startswith("http://") or video_url.startswith("https://"):
            await download_file(video_url, video_path)
        else:
            shutil.copy(video_url, video_path)

        logger.info(f"🎥 3D preview generated: {video_path}")
        return {"video_filepath": str(video_path), "subtitles": subtitles}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error in 3D preview generation: {e}")
        raise HTTPException(status_code=500, detail="Error generating 3D preview.")

@app.post("/generate_model")
async def generate_model(file: UploadFile = File(...)):
    """
    Accepts an image file upload and generates a 3D model.
    Returns the GLB model file path.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_location = DATA_DIR / f"{timestamp}_uploaded.png"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"📂 Uploaded file saved: {file_location}")

        # Run the common 3D conversion to (at least) trigger the necessary processing
        await process_3d_job(file_location, timestamp)

        # Extract the GLB model (which internally also runs gaussian extraction)
        glb_filepath = await extract_glb_async(timestamp)
        if not glb_filepath:
            raise HTTPException(status_code=500, detail="GLB extraction failed.")

        logger.info(f"🗿 3D model (GLB) generated: {glb_filepath}")
        return {"glb_filepath": glb_filepath}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error in GLB model generation: {e}")
        raise HTTPException(status_code=500, detail="Error generating GLB model.")

# -------------------------
# Graceful shutdown
# -------------------------
@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()
