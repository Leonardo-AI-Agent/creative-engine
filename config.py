import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file.
load_dotenv()

# Fetch API token and check.
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
if not HUGGINGFACE_API_TOKEN:
    raise ValueError("Hugging Face API token is not set in the .env file.")

# Global constants for models.
HF_MODEL = "whiteyhat/Flux-TRELLIS"
BG_MODEL = "not-lain/background-removal"

# Get ports from environment (defaults: 8000 for general endpoints, 8020 for chat streaming).
# CHAT_BASE_URL = os.getenv("CHAT_URL")
CHAT_BASE_URL = "http://localhost:8000"

# Data directory for saving files.
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
