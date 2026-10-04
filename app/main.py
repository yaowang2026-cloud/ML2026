import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.extraction import InvalidExtractionResponse, OllamaExtractor
from app.schemas import ExtractionResponse, OCRExtractionRequest


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite4.2:3b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    ).split(",")
    if origin.strip()
]


def create_app(extractor: OllamaExtractor | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        client: httpx.Client | None = None
        if extractor is None:
            client = httpx.Client(
                base_url=OLLAMA_URL,
                timeout=httpx.Timeout(OLLAMA_TIMEOUT_SECONDS),
            )
            application.state.extractor = OllamaExtractor(OLLAMA_MODEL, client)
        else:
            application.state.extractor = extractor
        try:
            yield
        finally:
            if client is not None:
                client.close()

    application = FastAPI(
        title="Maternal Registry OCR Extraction API",
        version="1.0.0",
        description=(
            "Extracts a fixed maternal-registry schema from OCR text. "
            "This service does not provide clinical advice."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post(
        "/api/v1/extract",
        response_model=ExtractionResponse,
        tags=["extraction"],
    )
    def extract(
        payload: OCRExtractionRequest,
        request: Request,
    ) -> ExtractionResponse:
        extractor: OllamaExtractor = request.app.state.extractor
        try:
            return extractor.extract(payload.ocr_text)
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="The extraction model timed out. Please retry.",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail="The extraction model is unavailable. Please retry.",
            ) from exc
        except InvalidExtractionResponse as exc:
            raise HTTPException(
                status_code=502,
                detail="The extraction model returned an invalid response. Please retry.",
            ) from exc

    return application


app = create_app()
