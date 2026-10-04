# ML2026
Machine Learning 2026 project

## OCR extraction API

The notebooks demonstrate extracting the maternal-registry fields from OCR
text. The production-facing API accepts that OCR text from a frontend and
returns the same 31-field extraction contract, including evidence and review
status for each field.

### Requirements

- Python 3.10 or newer
- Ollama reachable from the API process
- The configured Ollama model pulled locally (default: `granite4.2:3b`)

Install and start the service from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull granite4.2:3b
uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

Configure `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`, and
`ALLOWED_ORIGINS` in the process environment (or load `.env` through your
deployment configuration). CORS allows only the configured frontend origins.
The service does not persist or log OCR request bodies. Do not expose it to the
public internet without adding your deployment's authentication and transport
security.

### Frontend request

Send the OCR text as JSON to `POST /api/v1/extract`:

```javascript
const response = await fetch("http://localhost:8000/api/v1/extract", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ ocr_text: ocrResult.text }),
});

if (!response.ok) {
  throw new Error(`Extraction failed (${response.status})`);
}

const extraction = await response.json();
```

The response is `{ "fields": [...] }`. Each field includes `field_name`,
`value`, `status`, `evidence`, `reason`, and `question`. `KNOWN` values are
supported by OCR evidence; `NEEDS_REVIEW` values include a clarification
question; unresolved or absent values are not silently accepted.

`GET /health` is a liveness check. Interactive API documentation is available
at `/docs` while the service is running.

### Tests

Run the service tests with:

```powershell
python -m unittest discover -s tests
```
