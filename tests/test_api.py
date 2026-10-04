import json
import unittest

import httpx
from fastapi.testclient import TestClient

from app.extraction import OllamaExtractor
from app.main import create_app
from tests.test_extraction import valid_fields


class ExtractionAPITests(unittest.TestCase):
    def test_frontend_ocr_text_returns_the_extraction_contract(self) -> None:
        model_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            model_paths.append(request.url.path)
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": json.dumps({"fields": valid_fields()}),
                    }
                },
            )

        ollama_client = httpx.Client(
            base_url="http://ollama.test",
            transport=httpx.MockTransport(handler),
        )
        extractor = OllamaExtractor("granite4.2:3b", ollama_client)
        try:
            with TestClient(create_app(extractor)) as frontend_client:
                response = frontend_client.post(
                    "/api/v1/extract",
                    json={"ocr_text": "pt 201\nAge: 28"},
                )
        finally:
            ollama_client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["fields"]), 31)
        self.assertEqual(payload["fields"][1]["value"], 28)
        self.assertEqual(payload["fields"][0]["evidence"], "pt 201")
        self.assertEqual(model_paths, ["/api/chat"])

    def test_rejects_blank_ocr_text(self) -> None:
        with TestClient(create_app()) as frontend_client:
            response = frontend_client.post(
                "/api/v1/extract",
                json={"ocr_text": "   "},
            )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
