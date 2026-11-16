
from pathlib import Path

from fastapi import HTTPException
from google.genai import types

from app.core.config import BASE_DIR, MODEL_NAME
from app.models.ocr_models import OcrBatchResponse

OCR_PROMPT_PATH = BASE_DIR / "app" / "prompts" / "ocr_prompt.txt"


def transcribe_handwritten_pages(image_parts, gemini_client):
    """Transcribe a batch of handwritten page images using Gemini."""

    if not OCR_PROMPT_PATH.is_file():
        raise HTTPException(
            status_code=500,
            detail="The OCR prompt file is missing.",
        )

    prompt = OCR_PROMPT_PATH.read_text(encoding="utf-8")

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                prompt,
                *image_parts,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=OcrBatchResponse,
            ),
        )

        if not response.text:
            raise HTTPException(
                status_code=502,
                detail="Gemini returned an empty transcription.",
            )

        parsed = OcrBatchResponse.model_validate_json(response.text)

        if len(parsed.pages) != len(image_parts):
            raise HTTPException(
                status_code=502,
                detail="OCR returned an incorrect number of pages.",
            )

        expected_numbers = list(range(1, len(image_parts) + 1))
        actual_numbers = [
            item.page_number for item in parsed.pages
        ]

        if actual_numbers != expected_numbers:
            raise HTTPException(
                status_code=502,
                detail="OCR returned invalid page numbering.",
            )

        return parsed

    except HTTPException:
        raise

    except (ValueError, TypeError) as error:
        print(
            f"OCR response validation failed: "
            f"{type(error).__name__}: {error}"
        )
        raise HTTPException(
            status_code=502,
            detail="Gemini returned an invalid OCR response.",
        ) from error

    except Exception as error:
        print(
            f"OCR provider request failed: "
            f"{type(error).__name__}: {error}"
        )
        raise HTTPException(
            status_code=502,
            detail="Batch OCR failed. Check the backend configuration.",
        ) from error
