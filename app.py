# app.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from loguru import logger
from http.client import RemoteDisconnected
from urllib3.exceptions import ProtocolError

from models import PromptRequest
from services.sketch_generator import generate_sketch
from services.model_generator import generate_3d_preview, generate_model
from services.file_handler import close_http_client

app = FastAPI()

# ---------------------------------------------------------------------------
# Global Middleware to Catch and Handle Connection Errors
# ---------------------------------------------------------------------------
@app.middleware("http")
async def catch_connection_errors(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except (RemoteDisconnected, ProtocolError) as conn_error:
        # Log the connection-related error and return a 503 response.
        logger.error(f"Connection error caught: {conn_error}")
        return JSONResponse(
            status_code=503,
            content={"detail": "Service temporarily unavailable due to connection issues. Please try again later."}
        )
    except Exception as exc:
        # Log any other unhandled exceptions and return a generic error.
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please try again later."}
        )

# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------
@app.post("/generate_sketch")
async def generate_sketch_endpoint(request: PromptRequest):
    try:
        image_filepath = await generate_sketch(request.prompt, request.style)
        return {"image_filepath": image_filepath}
    except Exception as e:
        logger.error(f"Unexpected error in generate_sketch_endpoint: {e}")
        raise HTTPException(status_code=500, detail="Error generating image.")

@app.post("/generate_3d_preview")
async def generate_3d_preview_endpoint(file: UploadFile = File(...)):
    try:
        result = await generate_3d_preview(file)
        return result
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error in generate_3d_preview_endpoint: {e}")
        raise HTTPException(status_code=500, detail="Error generating 3D preview.")

@app.post("/generate_model")
async def generate_model_endpoint(file: UploadFile = File(...)):
    try:
        glb_filepath = await generate_model(file)
        return {"glb_filepath": glb_filepath}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error in generate_model_endpoint: {e}")
        raise HTTPException(status_code=500, detail="Error generating GLB model.")

# -----------------------------------------------------------------------------
# Graceful Shutdown
# -----------------------------------------------------------------------------
@app.on_event("shutdown")
async def shutdown_event():
    await close_http_client()
