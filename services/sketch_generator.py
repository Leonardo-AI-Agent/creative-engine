# services/sketch_generator.py
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from loguru import logger
from gradio_client import Client, handle_file

from config import DATA_DIR, HF_MODEL, BG_MODEL, HUGGINGFACE_API_TOKEN
from services.file_handler import fetch_or_copy_file

# Mapping for style enhancements.
STYLE_DESCRIPTIONS = {
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

# Initialize the background removal client.
bg_client = Client(BG_MODEL)

async def generate_sketch(prompt: str, style: str = None) -> str:
    """
    Generates an image (sketch) from the text prompt with an optional style,
    then removes the background using an external service.
    
    Returns:
        The local file path of the final, background-removed image.
    """
    try:
        # Append style description if provided.
        updated_prompt = prompt
        if style:
            if style in STYLE_DESCRIPTIONS:
                updated_prompt = f"{prompt}. {STYLE_DESCRIPTIONS[style]}"
            else:
                logger.warning(f"Style '{style}' not recognized. Using original prompt.")
        
        logger.info(f"Generating flux image for prompt: {updated_prompt}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_local_path = DATA_DIR / f"{timestamp}_flux_image.png"
        
        # Generate the image via the HuggingFace model.
        hf_client = Client(HF_MODEL, hf_token=HUGGINGFACE_API_TOKEN)
        image_result = await asyncio.to_thread(
            hf_client.predict,
            prompt=updated_prompt,
            seed=42,
            randomize_seed=True,
            width=1024,
            height=1024,
            guidance_scale=3.5,
            api_name="/generate_flux_image"
        )
        await fetch_or_copy_file(image_result, image_local_path)
        logger.info(f"Flux image saved: {image_local_path}")

        # Remove background using the background removal client.
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
        logger.info(f"Background removed image saved: {image_bg_local_path}")
        return str(image_bg_local_path)
    
    except Exception as e:
        logger.error(f"Error in generate_sketch: {e}")
        raise HTTPException(status_code=500, detail="Error generating image.")
