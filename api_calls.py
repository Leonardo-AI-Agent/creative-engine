import httpx

def stream_chat(question: str, user_id: str, chat_base_url: str):
    """
    Streams the answer from the chat endpoint, yielding each chunk.
    Uses iter_lines() for robust streaming of line-delimited responses.
    """
    payload = {"question": question, "user_id": user_id}
    try:
        with httpx.Client(timeout=None) as client:
            with client.stream("POST", f"{chat_base_url}/query/stream", json=payload) as response:
                # Iterate over each line in the response.
                for line in response.iter_lines():
                    if line:  # ignore empty lines
                        # Decode bytes to string if necessary.
                        yield line.decode("utf-8") if isinstance(line, bytes) else line
    except Exception as e:
        # If an error occurs, yield a single chunk with the error message.
        yield f"Error during streaming: {str(e)}"
