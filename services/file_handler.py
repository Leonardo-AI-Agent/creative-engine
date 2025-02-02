import asyncio
import shutil
import httpx
import aiofiles
from pathlib import Path
from fastapi import HTTPException
from loguru import logger

# Create a single async HTTP client instance for file downloads.
http_client = httpx.AsyncClient(timeout=120.0)

async def download_file(url: str, local_path: Path) -> None:
    """
    Downloads a file asynchronously via HTTP and saves it using aiofiles.
    """
    try:
        async with http_client.stream("GET", url) as response:
            response.raise_for_status()
            async with aiofiles.open(local_path, "wb") as out_file:
                async for chunk in response.aiter_bytes():
                    await out_file.write(chunk)
        logger.info(f"✅ File downloaded: {local_path}")
    except httpx.HTTPError as e:
        logger.error(f"❌ Download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download file.")

async def fetch_or_copy_file(source: str, destination: Path) -> None:
    """
    Downloads a file if `source` is a URL; otherwise, copies the file from a local path.
    Uses asyncio.to_thread() for blocking operations.
    """
    if source.startswith("http://") or source.startswith("https://"):
        await download_file(source, destination)
    else:
        try:
            await asyncio.to_thread(shutil.copy, source, destination)
            logger.info(f"✅ File copied to: {destination}")
        except Exception as e:
            logger.error(f"❌ File copy error: {e}")
            raise HTTPException(status_code=500, detail="Failed to copy file.")

async def save_upload_file(upload_file, destination: Path) -> None:
    """
    Asynchronously saves an uploaded file to the destination using aiofiles.
    """
    try:
        content = await upload_file.read()
        async with aiofiles.open(destination, "wb") as out_file:
            await out_file.write(content)
        logger.info(f"📂 Uploaded file saved: {destination}")
    except Exception as e:
        logger.error(f"❌ Error saving uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")

async def close_http_client() -> None:
    """
    Gracefully closes the asynchronous HTTP client.
    """
    await http_client.aclose()
