import asyncio
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File
from loguru import logger
from gradio_client import Client, handle_file

from config import DATA_DIR, HF_MODEL, BG_MODEL, HUGGINGFACE_API_TOKEN
from models import PromptRequest
from services.processing import process_3d_job, extract_glb_async
from services.file_handler import fetch_or_copy_file, save_upload_file, close_http_client

# Initialize FastAPI app.
app = FastAPI()

# Initialize a background removal client.
bg_client = Client(BG_MODEL)

# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.post("/generate_sketch")
async def generate_sketch(request: PromptRequest):
    """
    Generates an image (sketch) from a text prompt (optionally enhanced by style).
    Removes the background using an external service.
    Returns the local file path of the final image.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
        updated_prompt = request.prompt
        if request.style:
            if request.style in style_descriptions:
                updated_prompt = f"{request.prompt}. {style_descriptions[request.style]}"
            else:
                logger.warning(f"Style '{request.style}' not recognized. Using original prompt.")

        logger.info(f"🖼️ Generating flux image for prompt: {updated_prompt}")

        # Generate the image via Gradio.
        image_result = await asyncio.to_thread(
            Client(HF_MODEL, hf_token=HUGGINGFACE_API_TOKEN).predict,
            prompt=updated_prompt,
            seed=42,
            randomize_seed=True,
            width=1024,
            height=1024,
            guidance_scale=3.5,
            api_name="/generate_flux_image"
        )
        image_local_path = DATA_DIR / f"{timestamp}_flux_image.png"
        await fetch_or_copy_file(image_result, image_local_path)
        logger.info(f"🎨 Image saved: {image_local_path}")

        # Remove background using the background removal service.
        bg_result = await asyncio.to_thread(
            bg_client.predict,
            image=handle_file(str(image_local_path)),
            api_name="/image"
        )
        if isinstance(bg_result, list):
            bg_result = bg_result[0]

        image_bg_local_path = DATA_DIR / f"{timestamp}_flux_image_bg.png"
        if isinstance(bg_result, str):
            await fetch_or_copy_file(bg_result, image_bg_local_path)
        else:
            raise HTTPException(status_code=500, detail="Invalid background removal result.")

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
        await save_upload_file(file, file_location)

        result = await process_3d_job(file_location, timestamp)
        video_url = result["video"]
        subtitles = result.get("subtitles", None)
        video_path = DATA_DIR / f"{timestamp}_3d_preview.mp4"
        await fetch_or_copy_file(video_url, video_path)
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
        await save_upload_file(file, file_location)

        await process_3d_job(file_location, timestamp)
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

# -----------------------------------------------------------------------------
# Graceful Shutdown
# -----------------------------------------------------------------------------

@app.on_event("shutdown")
async def shutdown_event():
    await close_http_client()
