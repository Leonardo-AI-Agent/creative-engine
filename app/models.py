from pydantic import BaseModel
from typing import Optional

class ImageRequest(BaseModel):
    """
    Pydantic model to validate the input request for generating a Flux image.
    """
    prompt: str
    seed: float = 42
    randomize_seed: bool = True
    width: int = 1024
    height: int = 1024
    guidance_scale: float = 3.5

    class Config:
        # Enable arbitrary types in JSON, like float, int, etc.
        orm_mode = True

class ImageTo3DRequest(BaseModel):
    """
    Pydantic model to validate the input request for generating a 3D object from an image.
    """
    image_url: str
    seed: float = 42
    ss_guidance_strength: float = 7.5
    ss_sampling_steps: int = 12
    slat_guidance_strength: float = 3.0
    slat_sampling_steps: int = 12

    class Config:
        orm_mode = True
