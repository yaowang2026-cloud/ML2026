import json
import math
import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.schemas import (
    BINARY_FIELDS,
    CODING_RULES,
    NUMERIC_FIELDS,
    TARGET_FIELDS,
    TEST_RESULT_FIELDS,
    YES_NO_FIELDS,
    ExtractionResponse,
    ExtractionStatus,
)


SYSTEM_PROMPT = """
You are a strict document-extraction engine for maternal registry forms.

You are NOT a clinical decision-support system. Do not diagnose, recommend
treatment, or infer a medical condition. Map only the supplied OCR text into
the supplied registry schema.

The OCR may be incomplete, unordered, duplicated, abbreviated, or noisy.
Search the entire document; do not assume field order or line boundaries.
Never invent a value, derive one field from another, or assign an unlabeled
number based on plausibility. Preserve the exact OCR fragment that supports
each value and use only the supplied coding rules.

Return every target field exactly once.

Statuses:
- KNOWN: sufficiently clear evidence supports the value.
- NEEDS_REVIEW: a plausible candidate exists but ambiguity remains; include a
  candidate when possible and one concise clarification question.
- ILLEGIBLE: relevant OCR text exists but cannot be interpreted reliably.
- NOT_PROVIDED: no supporting OCR evidence exists; value and evidence must be
  null.

Return JSON only and follow the supplied schema exactly. For KNOWN, include
the exact supporting OCR fragment as evidence. Prefer NEEDS_REVIEW over
guessing. Do not provide clinical advice.
""".strip()

FEW_SHOT_EXAMPLES = [
    {
        "input": "g2 p1 a0",
        "lesson": {
            "gravidity (number)": {"value": 2, "status": "KNOWN", "evidence": "g2"},
            "parity (number)": {"value": 1, "status": "KNOWN", "evidence": "p1"},
            "abortions (number)": {"value": 0, "status": "KNOWN", "evidence": "a0"},
        },
    },
    {
        "input": "hiv neg   hcv neg",
        "lesson": {
            "hiv test result": {
                "value": 0,
                "status": "KNOWN",
                "evidence": "hiv neg",
            },
            "hepatitis c test result": {
                "value": 0,
                "status": "KNOWN",
                "evidence": "hcv neg",
            },
        },
    },
    {
        "input": "bp 12O/8O",
        "lesson": {
            "mean systolic bp (mmhg)": {
                "value": 120,
                "status": "NEEDS_REVIEW",
                "evidence": "bp 12O/8O",
                "reason": "OCR may have confused O with 0.",
                "question": "I read the blood pressure as 120/80. Is that correct?",
            },
            "mean diastolic bp (mmhg)": {
                "value": 80,
                "status": "NEEDS_REVIEW",
                "evidence": "bp 12O/8O",
                "reason": "OCR may have confused O with 0.",
                "question": "I read the blood pressure as 120/80. Is that correct?",
            },
        },
    },
    {
        "input": "24.8",
        "lesson": {
            "bmi pregestational (kg/m2)": {
                "value": 24.8,
                "status": "NEEDS_REVIEW",
                "evidence": "24.8",
                "reason": "The number is unlabeled.",
                "question": "Is 24.8 the pregestational BMI?",
            }
        },
    },
    {
        "input": "syph ____",
        "lesson": {
            "syphilis test result": {
                "value": None,
                "status": "ILLEGIBLE",
                "evidence": "syph ____",
                "reason": "The field appears present but the result is unreadable.",
                "question": "What is the syphilis test result?",
            }
        },
    },
]


class InvalidExtractionResponse(RuntimeError):
    """Raised when Ollama cannot produce a valid registry extraction."""


def build_user_prompt(ocr_text: str) -> str:
    schema_example = {
        "fields": [
            {
                "field_name": "id",
                "value": "201",
                "status": "KNOWN",
                "evidence": "pt 201",
                "reason": None,
                "question": None,
            }
        ]
    }
    return "\n\n".join(
        (
            "TARGET REGISTRY FIELDS\n" + json.dumps(TARGET_FIELDS, indent=2),
            "CODING RULES\n" + json.dumps(CODING_RULES, indent=2),
            "FEW-SHOT BEHAVIOR EXAMPLES\n"
            + json.dumps(FEW_SHOT_EXAMPLES, indent=2),
            "RESPONSE SHAPE EXAMPLE\n" + json.dumps(schema_example, indent=2),
            "CURRENT OCR DOCUMENT\n---BEGIN OCR---\n"
            + ocr_text
            + "\n---END OCR---",
            f"Extract all {len(TARGET_FIELDS)} fields exactly once. Return JSON "
            "matching the supplied schema. Missing information must remain "
            "missing; uncertain information must be marked NEEDS_REVIEW.",
        )
    )


def _normalize_value(field_name: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value

    normalized = value.strip().lower()
    if normalized == "":
        return None

    if field_name in NUMERIC_FIELDS:
        try:
            number = float(normalized)
        except ValueError:
            return value
        if not math.isfinite(number):
            return value
        return int(number) if number.is_integer() else number

    if field_name in YES_NO_FIELDS:
        if normalized in {"yes", "no"}:
            return int(normalized == "yes")
        if normalized in {"0", "1"}:
            return int(normalized)

    if field_name in TEST_RESULT_FIELDS:
        if normalized in {"negative", "positive"}:
            return int(normalized == "positive")
        if normalized in {"0", "1"}:
            return int(normalized)

    category_codes = CODING_RULES.get(field_name)
    if category_codes is not None:
        if normalized in category_codes:
            return category_codes[normalized]
        if normalized.isdigit():
            return int(normalized)

    return value


def _parse_model_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response was not valid JSON.") from exc

    if isinstance(payload, list):
        payload = {"fields": payload}
    if not isinstance(payload, dict) or not isinstance(payload.get("fields"), list):
        raise ValueError("Model response did not contain a fields list.")

    fields = []
    for item in payload["fields"]:
        if not isinstance(item, dict):
            raise ValueError("Model response contained an invalid field.")
        normalized = dict(item)
        name = normalized.get("field_name")
        if isinstance(name, str):
            normalized["value"] = _normalize_value(name, normalized.get("value"))
        status = normalized.get("status")
        if isinstance(status, str):
            normalized["status"] = status.strip().upper()
        for key in ("value", "evidence", "reason", "question"):
            if normalized.get(key) == "":
                normalized[key] = None
        fields.append(normalized)
    return {"fields": fields}


def validate_application_rules(
    extraction: ExtractionResponse,
    ocr_text: str,
) -> None:
    for item in extraction.fields:
        value = item.value

        if item.field_name in BINARY_FIELDS and value is not None:
            if type(value) is not int or value not in {0, 1}:
                raise ValueError(f"Invalid binary code for {item.field_name}.")

        if item.field_name == "education level (0=none/primary,1=secondary,2=higher)":
            if value is not None and (type(value) is not int or value not in {0, 1, 2}):
                raise ValueError("Invalid education-level code.")

        if item.field_name in NUMERIC_FIELDS and value is not None:
            if type(value) not in {int, float}:
                raise ValueError(f"Expected a numeric value for {item.field_name}.")

        if item.status == ExtractionStatus.NOT_PROVIDED:
            if value is not None or item.evidence is not None:
                raise ValueError(
                    f"{item.field_name}: NOT_PROVIDED requires null value and evidence."
                )
        elif item.status in {
            ExtractionStatus.KNOWN,
            ExtractionStatus.NEEDS_REVIEW,
            ExtractionStatus.ILLEGIBLE,
        } and not item.evidence:
            raise ValueError(f"{item.field_name}: this status requires OCR evidence.")

        if item.status == ExtractionStatus.NEEDS_REVIEW and not item.question:
            raise ValueError(f"{item.field_name}: NEEDS_REVIEW requires a question.")

        if item.evidence is not None and item.evidence not in ocr_text:
            raise ValueError(f"{item.field_name}: evidence is not an exact OCR fragment.")


class OllamaExtractor:
    def __init__(
        self,
        model: str,
        client: httpx.Client,
    ) -> None:
        self._model = model
        self._client = client

    def extract(self, ocr_text: str) -> ExtractionResponse:
        prompt = build_user_prompt(ocr_text)
        retry_note = ""

        for attempt in range(2):
            response = self._client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt + retry_note},
                    ],
                    "format": ExtractionResponse.model_json_schema(),
                    "options": {"temperature": 0, "num_predict": 8192},
                    "think": False,
                    "keep_alive": "10m",
                    "stream": False,
                },
            )
            response.raise_for_status()

            try:
                body = response.json()
                message = body.get("message") if isinstance(body, dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Ollama response did not contain model content.")
                normalized = _parse_model_content(content)
                extraction = ExtractionResponse.model_validate(normalized)
                validate_application_rules(extraction, ocr_text)
            except (ValueError, ValidationError) as exc:
                if attempt == 0:
                    retry_note = (
                        "\n\nYour previous response was invalid. Re-read the full "
                        "OCR and return one complete JSON object with all target "
                        "fields exactly once. Evidence must be copied exactly "
                        "from the OCR; use null value and evidence for "
                        "NOT_PROVIDED fields."
                    )
                    continue
                raise InvalidExtractionResponse(
                    "Ollama returned an invalid extraction after one retry."
                ) from exc

            return extraction

        raise InvalidExtractionResponse("Extraction failed after one retry.")
