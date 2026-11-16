"""Offline tests for Inkora AI's evaluation endpoint.

Run from the backend folder:
    python -m unittest test_evaluation_api.py -v

The tests replace Gemini with a deterministic fake client; no API call or key is needed.
"""
import io
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import app.routers.evaluation as evaluation_router
import main
from app.models.evaluation_models import EvaluationResponse
from app.services.evaluation_service import validate_evaluation_result

VALID_EVALUATION = {
    "evaluation_status": "evaluated",
    "marks_awarded": 7.5,
    "total_marks": 10,
    "score_rationale": "The main concept is correct, but an important detail is missing.",
    "feedback_summary": "Good understanding, with one important detail missing.",
    "clarification_needed": None,
    "scoring_breakdown": [
        {
            "criterion": "Core concept",
            "marks_awarded": 4.0,
            "marks_possible": 5.0,
            "comment": "The central concept is mostly correct.",
        },
        {
            "criterion": "Explanation",
            "marks_awarded": 2.5,
            "marks_possible": 4.0,
            "comment": "One important detail is missing.",
        },
        {
            "criterion": "Example",
            "marks_awarded": 1.0,
            "marks_possible": 1.0,
            "comment": "The example is relevant.",
        },
    ],
    "feedback": {
        "strengths": ["The central concept is mostly correct."],
        "missing_or_weak_points": ["One important detail is missing."],
        "improvements": ["Explain the missing detail."],
        "ways_to_gain_more_marks": ["Add a relevant explanation."],
    },
}


class FakeResponse:
    def __init__(self, payload):
        self.text = json.dumps(payload)


class FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        config = kwargs.get("config")
        schema = (
            config.get("response_schema")
            if isinstance(config, dict)
            else getattr(config, "response_schema", None)
        )
        schema_name = getattr(schema, "__name__", "")

        if schema_name == "EvaluationOcrResponse":
            page_count = len(kwargs["contents"]) - 1
            return FakeResponse({
                "pages": [
                    {"page_number": i + 1, "transcription": f"Transcribed page {i + 1}"}
                    for i in range(page_count)
                ]
            })

        payload = json.loads(json.dumps(VALID_EVALUATION))
        # The fake result is valid for the standard test total of 10 marks.
        return FakeResponse(payload)


class FakeClient:
    def __init__(self):
        self.models = FakeModels()


class EvaluationApiTests(unittest.TestCase):
    def setUp(self):
        self.fake_client = FakeClient()
        self.client_patch = patch.object(
            evaluation_router,
            "client",
            self.fake_client,
        )
        self.client_patch.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client_patch.stop()

    def common_data(self):
        return {
            "total_marks": "10",
            "academic_level": "Undergraduate",
            "degree_field": "MCA",
        }

    def make_png(self):
        image = Image.new("RGB", (32, 32), "white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_typed_evaluation_returns_pdf_and_score_headers(self):
        data = self.common_data()
        data.update({
            "question_text": "Explain database normalization.",
            "student_answer_text": "Normalization reduces redundancy.",
        })
        response = self.client.post("/api/evaluate", data=data)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(response.headers["x-marks-awarded"], "7.5")
        self.assertEqual(response.headers["x-total-marks"], "10.0")
        self.assertEqual(len(self.fake_client.models.calls), 1)

    def test_blank_answer_is_awarded_zero_without_grading_call(self):
        data = self.common_data()
        data["question_text"] = "Explain database normalization."
        response = self.client.post("/api/evaluate", data=data)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["x-marks-awarded"], "0")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(len(self.fake_client.models.calls), 0)

    def test_handwritten_question_and_answer_images_return_pdf(self):
        data = self.common_data()
        image_bytes = self.make_png()
        response = self.client.post(
            "/api/evaluate",
            data=data,
            files=[
                ("question_image", ("question.png", image_bytes, "image/png")),
                ("student_answer_images", ("answer.png", image_bytes, "image/png")),
            ],
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        # One OCR request and one grading request for the two images.
        self.assertEqual(len(self.fake_client.models.calls), 2)

    def test_question_text_and_image_cannot_both_be_supplied(self):
        data = self.common_data()
        data.update({
            "question_text": "A typed question",
            "student_answer_text": "An answer",
        })
        response = self.client.post(
            "/api/evaluate",
            data=data,
            files=[("question_image", ("question.png", self.make_png(), "image/png"))],
        )
        self.assertEqual(response.status_code, 400)

    def test_typed_answer_and_answer_images_cannot_both_be_supplied(self):
        data = self.common_data()
        data.update({
            "question_text": "A typed question",
            "student_answer_text": "A typed answer",
        })
        response = self.client.post(
            "/api/evaluate",
            data=data,
            files=[("student_answer_images", ("answer.png", self.make_png(), "image/png"))],
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_score_is_rejected_by_server_validation(self):
        result = EvaluationResponse.model_validate(VALID_EVALUATION)
        invalid = result.model_copy(update={"marks_awarded": 11.0})
        with self.assertRaises(ValueError):
            validate_evaluation_result(invalid, 10.0)

    def test_invalid_total_is_rejected_by_server_validation(self):
        result = EvaluationResponse.model_validate(VALID_EVALUATION)
        invalid = result.model_copy(update={"total_marks": 9.0})
        with self.assertRaises(ValueError):
            validate_evaluation_result(invalid, 10.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
