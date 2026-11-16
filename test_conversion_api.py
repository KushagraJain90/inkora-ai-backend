
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.routers.conversion as conversion_router
import main


class FakeGeminiClient:
    pass


class ConversionApiTests(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(main.app)

        self.gemini_patch = patch.object(
            conversion_router,
            "client",
            FakeGeminiClient(),
        )
        self.gemini_patch.start()

        self.libreoffice_patch = patch.object(
            conversion_router,
            "LIBREOFFICE_PATH",
            Path(__file__),
        )
        self.libreoffice_patch.start()

    def tearDown(self):
        self.gemini_patch.stop()
        self.libreoffice_patch.stop()

    def test_upload_requires_at_least_one_page(self):
        response = self.client.post(
            "/api/convert",
            files=[],
        )

        self.assertEqual(response.status_code, 422)

    def test_upload_rejects_more_than_100_pages(self):
        image_bytes = b"test image"

        files = [
            (
                "pages",
                (f"page_{index}.jpg", image_bytes, "image/jpeg"),
            )
            for index in range(101)
        ]

        response = self.client.post(
            "/api/convert",
            files=files,
        )

        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_unsupported_file_type(self):
        response = self.client.post(
            "/api/convert",
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
            "/api/convert",
            files=[
                (
                    "pages",
                    ("empty.jpg", b"", "image/jpeg"),
                )
            ],
        )

        self.assertEqual(response.status_code, 400)

    @patch("app.routers.conversion.create_conversion_zip")
    @patch("app.routers.conversion.convert_docx_to_pdf")
    @patch("app.routers.conversion.build_word_document")
    @patch("app.routers.conversion.process_conversion_pages")
    def test_valid_upload_returns_zip(
        self,
        mock_process,
        mock_build_docx,
        mock_convert_pdf,
        mock_create_zip,
    ):
        mock_process.return_value = [
            {
                "page_number": 1,
                "transcription": "Test transcription",
                "visual_images": {},
            }
        ]

        mock_create_zip.return_value = b"fake zip content"

        response = self.client.post(
            "/api/convert",
            files=[
                (
                    "pages",
                    ("page1.jpg", b"test image", "image/jpeg"),
                )
            ],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-type"],
            "application/zip",
        )
        self.assertEqual(response.content, b"fake zip content")
        self.assertEqual(response.headers["X-Page-Count"], "1")
        self.assertIn(
            "Inkora_AI_Converted.zip",
            response.headers["Content-Disposition"],
        )

        mock_process.assert_called_once()
        mock_build_docx.assert_called_once()
        mock_convert_pdf.assert_called_once()
        mock_create_zip.assert_called_once()


if __name__ == "__main__":
    unittest.main()
