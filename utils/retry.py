import asyncio
from loguru import logger
from typing import Any, Callable

async def retry_async(
    func: Callable[..., Any],
    retries: int = 3,
    initial_delay: int = 5,
    **kwargs
) -> Any:
    """
    Asynchronously call `func` with provided kwargs and retry on failure.
    """
    delay = initial_delay
    for attempt in range(retries):
        try:
            result = await func(**kwargs)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{retries} failed: {e}. Retrying in {delay} seconds.")
        await asyncio.sleep(delay)
        delay *= 2  # exponential backoff
    logger.error("Failed after multiple attempts.")
    return None
