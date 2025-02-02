from app.config import settings
from gradio_client import Client, handle_file
from loguru import logger
from typing import Any

# Initialize the Hugging Face Client
hf_client = Client(settings.HUGGINGFACE_MODEL)

async def generate_flux_image_service(request: Any) -> str:
    """
    Interacts with the Hugging Face model to generate an image based on the provided prompt.

    Parameters:
    - request: The incoming request body containing parameters like prompt, seed, width, etc.

    Returns:
    - The file path of the generated image.
    """
    try:
        logger.debug(f"Request parameters for image generation: {request.dict()}")

        # Make the prediction call to Hugging Face
        result = hf_client.predict(
            prompt=request.prompt,
            seed=request.seed,
            randomize_seed=request.randomize_seed,
            width=request.width,
            height=request.height,
            guidance_scale=request.guidance_scale,
            api_name="/generate_flux_image"
        )

        logger.debug(f"Flux image generated: {result}")
        return result  # Assuming the response contains the file path for the generated image

    except Exception as e:
        logger.error(f"Error while generating image: {e}")
        raise Exception(f"Failed to generate image: {e}")

async def image_to_3d_service(request: Any) -> str:
    """
    Interacts with the Hugging Face model to generate a 3D object from an image URL.

    Parameters:
    - request: The incoming request body containing parameters like image_url, seed, strength, etc.

    Returns:
    - The file path of the generated 3D object.
    """
    try:
        logger.debug(f"Request parameters for 3D object generation: {request.dict()}")

        # Make the prediction call to Hugging Face for 3D object generation
        result = hf_client.predict(
            image=handle_file(request.image_url),
            seed=request.seed,
            ss_guidance_strength=request.ss_guidance_strength,
            ss_sampling_steps=request.ss_sampling_steps,
            slat_guidance_strength=request.slat_guidance_strength,
            slat_sampling_steps=request.slat_sampling_steps,
            api_name="/image_to_3d"
        )

        logger.debug(f"3D object generated: {result}")
        return result  # Assuming the response contains the file path for the generated 3D object

    except Exception as e:
        logger.error(f"Error while generating 3D object: {e}")
        raise Exception(f"Failed to generate 3D object: {e}")
