
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

# Backend root directory
BASE_DIR = Path(__file__).resolve().parents[2]

# Load environment variables from the backend root
load_dotenv(BASE_DIR / ".env")

# Gemini configuration
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Image upload configuration
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per image

# Processing configuration
BATCH_SIZE = 4
MAX_CONVERSION_PAGES = 100

# LibreOffice configuration
# Can be overridden using the LIBREOFFICE_PATH environment variable.
libreoffice_env = os.getenv("LIBREOFFICE_PATH")

if libreoffice_env:
    LIBREOFFICE_PATH = Path(libreoffice_env)
else:
    detected_path = shutil.which("soffice")

    if detected_path:
        LIBREOFFICE_PATH = Path(detected_path)
    else:
        LIBREOFFICE_PATH = Path(
            r"C:\Program Files\LibreOffice\program\soffice.exe"
        )
