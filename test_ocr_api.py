
import io
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import main
import app.routers.ocr as ocr_router


class FakeGeminiClient:
    pass


class OcrApiTests(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(main.app)
        self.gemini_patch = patch.object(
            ocr_router,
            "client",
            FakeGeminiClient(),
        )
        self.gemini_patch.start()

    def tearDown(self):
        self.gemini_patch.stop()

    @staticmethod
    def create_test_image():
        image = Image.new("RGB", (100, 100), color="white")
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="JPEG")
        return image_bytes.getvalue()

    def test_upload_requires_at_least_one_page(self):
        response = self.client.post(
            "/api/ocr",
            files=[],
        )
        self.assertEqual(response.status_code, 422)

    def test_upload_rejects_more_than_four_pages(self):
        image_bytes = self.create_test_image()

        files = [
            (
                "pages",
                (f"page_{index}.jpg", image_bytes, "image/jpeg"),
            )
            for index in range(5)
        ]

        response = self.client.post("/api/ocr", files=files)

        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_unsupported_file_type(self):
        response = self.client.post(
            "/api/ocr",
            files=[
                (
                    "pages",
                    ("page.txt", b"not an image", "text/plain"),
                )
            ],
        )

        self.assertEqual(response.status_code, 415)

    def test_upload_rejects_empty_image(self):
        response = self.client.post(
            "/api/ocr",
            files=[
                (
                    "pages",
                    ("empty.jpg", b"", "image/jpeg"),
                )
            ],
        )

        self.assertEqual(response.status_code, 400)

    @patch(
        "app.routers.ocr.transcribe_handwritten_pages"
    )
    def test_valid_upload_returns_transcription(
        self,
        mock_transcribe,
    ):
        from app.models.ocr_models import (
            OcrBatchResponse,
            PageTranscription,
        )

        mock_transcribe.return_value = OcrBatchResponse(
            pages=[
                PageTranscription(
                    page_number=1,
                    transcription="This is a test transcription.",
                    visual_regions=[],
                )
            ]
        )

        image_bytes = self.create_test_image()

        response = self.client.post(
            "/api/ocr",
            files=[
                (
                    "pages",
                    ("page1.jpg", image_bytes, "image/jpeg"),
                )
            ],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page_count"], 1)
        self.assertEqual(response.json()["batch_request_count"], 1)
        self.assertEqual(
            response.json()["pages"][0]["transcription"],
            "This is a test transcription.",
        )

        mock_transcribe.assert_called_once()


if __name__ == "__main__":
    unittest.main()
