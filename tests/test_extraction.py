import json
import unittest
from collections.abc import Callable

import httpx

from app.extraction import InvalidExtractionResponse, OllamaExtractor
from app.schemas import ExtractionStatus, TARGET_FIELDS


def valid_fields() -> list[dict[str, object]]:
    fields = [
        {
            "field_name": name,
            "value": None,
            "status": "NOT_PROVIDED",
            "evidence": None,
            "reason": None,
            "question": None,
        }
        for name in TARGET_FIELDS
    ]
    fields[0] = {
        "field_name": "id",
        "value": "patient-201",
        "status": "KNOWN",
        "evidence": "pt 201",
        "reason": None,
        "question": None,
    }
    fields[1] = {
        "field_name": "age (years)",
        "value": "28",
        "status": "KNOWN",
        "evidence": "Age: 28",
        "reason": None,
        "question": None,
    }
    return fields


class OllamaExtractorTests(unittest.TestCase):
    def make_extractor(
        self,
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> tuple[OllamaExtractor, httpx.Client]:
        client = httpx.Client(
            base_url="http://ollama.test",
            transport=httpx.MockTransport(handler),
        )
        return OllamaExtractor("granite4.2:3b", client), client

    def test_extracts_and_normalizes_a_complete_response(self) -> None:
        requested: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(request)
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps({"fields": valid_fields()})}},
            )

        extractor, client = self.make_extractor(handler)
        try:
            result = extractor.extract("pt 201\nAge: 28")
        finally:
            client.close()

        self.assertEqual(len(result.fields), len(TARGET_FIELDS))
        self.assertEqual(result.fields[1].value, 28)
        self.assertEqual(result.fields[0].status, ExtractionStatus.KNOWN)
        self.assertEqual(requested[0].url.path, "/api/chat")
        self.assertEqual(
            json.loads(requested[0].content)["model"],
            "granite4.2:3b",
        )

    def test_retries_once_after_invalid_model_output(self) -> None:
        calls = 0
        prompts: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            request_body = json.loads(request.content)
            prompts.append(request_body["messages"][1]["content"])
            fields = valid_fields()
            if calls == 1:
                fields.pop()
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps({"fields": fields})}},
            )

        extractor, client = self.make_extractor(handler)
        try:
            result = extractor.extract("pt 201\nAge: 28")
        finally:
            client.close()

        self.assertEqual(calls, 2)
        self.assertEqual(len(result.fields), len(TARGET_FIELDS))
        self.assertIn("Your previous response was invalid", prompts[1])

    def test_rejects_evidence_not_present_in_ocr_after_retry(self) -> None:
        calls = 0
        paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            paths.append(request.url.path)
            fields = valid_fields()
            fields[0]["evidence"] = "invented evidence"
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps({"fields": fields})}},
            )

        extractor, client = self.make_extractor(handler)
        try:
            with self.assertRaises(InvalidExtractionResponse):
                extractor.extract("pt 201\nAge: 28")
        finally:
            client.close()
        self.assertEqual(calls, 2)
        self.assertEqual(paths, ["/api/chat", "/api/chat"])


if __name__ == "__main__":
    unittest.main()
