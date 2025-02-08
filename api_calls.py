import httpx
from loguru import logger

def stream_chat(question: str, user_id: str, chat_base_url: str):
    """
    Streams the answer from the chat endpoint, yielding each chunk.
    Uses iter_lines() for robust streaming of line-delimited responses.
    """
    logger.info("stream_chat: Starting stream for question '{}' and user_id '{}'", question, user_id)
    payload = {"question": question, "user_id": user_id}
    try:
        with httpx.Client(timeout=None) as client:
            url = f"{chat_base_url}/query/stream"
            logger.info("stream_chat: Sending POST request to '{}' with payload: {}", url, payload)
            with client.stream("POST", url, json=payload) as response:
                logger.info("stream_chat: Received response with status code {}", response.status_code)
                # Iterate over each line in the response.
                for line in response.iter_lines():
                    if line:  # ignore empty lines
                        chunk = line.decode("utf-8") if isinstance(line, bytes) else line
                        logger.debug("stream_chat: Received chunk: {}", chunk)
                        yield chunk
    except Exception as e:
        logger.exception("stream_chat: Exception during streaming")
        yield f"Error during streaming: {str(e)}"
