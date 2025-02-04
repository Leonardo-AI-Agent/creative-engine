# services/model_generator.py
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from loguru import logger

from config import DATA_DIR
from services.file_handler import save_upload_file, fetch_or_copy_file
from services.processing import process_3d_job, extract_glb_async

async def generate_3d_preview(upload_file: UploadFile) -> dict:
    """
    Accepts an image upload, saves it, generates a 3D preview (video),
    and returns the video file path along with any subtitles.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_location = DATA_DIR / f"{timestamp}_uploaded.png"
        await save_upload_file(upload_file, file_location)
        
        result = await process_3d_job(file_location, timestamp)
        video_url = result["video"]
        subtitles = result.get("subtitles")
        video_path = DATA_DIR / f"{timestamp}_3d_preview.mp4"
        await fetch_or_copy_file(video_url, video_path)
        logger.info(f"3D preview generated: {video_path}")
        return {"video_filepath": str(video_path), "subtitles": subtitles}
    
    except Exception as e:
        logger.error(f"Error generating 3D preview: {e}")
        raise HTTPException(status_code=500, detail="Error generating 3D preview.")

async def generate_model(upload_file: UploadFile) -> str:
    """
    Accepts an image upload, saves it, processes it to generate a 3D model,
    and returns the GLB file path.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_location = DATA_DIR / f"{timestamp}_uploaded.png"
        await save_upload_file(upload_file, file_location)
        
        await process_3d_job(file_location, timestamp)
        glb_filepath = await extract_glb_async(timestamp)
        if not glb_filepath:
            raise HTTPException(status_code=500, detail="GLB extraction failed.")
        
        logger.info(f"3D model (GLB) generated: {glb_filepath}")
        return glb_filepath
    
    except Exception as e:
        logger.error(f"Error generating GLB model: {e}")
        raise HTTPException(status_code=500, detail="Error generating GLB model.")
