
from google import genai

from app.core.config import API_KEY

# Create one shared Gemini client for the application.
client = genai.Client(api_key=API_KEY) if API_KEY else None


def get_gemini_client():
    """
    Return the configured Gemini client.

    Raise an error if the API key is missing.
    """
    if client is None:
        raise RuntimeError(
            "Gemini API key is not configured on the server."
        )

    return client
