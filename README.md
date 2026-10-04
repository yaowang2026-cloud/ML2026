# DayOne: multi-photo registry extraction

The frontend and notebook share the same local Ollama backend. The original files are in `original-backup/`.

## Run

From this directory, using Python 3.10 or newer:

```powershell
python -m pip install -r backend/requirements.txt
python backend/app.py
```

Open http://127.0.0.1:5001. Ollama must be running with `qwen3.5:9b` installed. Set `OLLAMA_MODEL` before startup to use another compatible vision model.

Alternatively, open the modified `granite42_ollama_maternal_extraction_example-2.ipynb`, run its setup cells, then call `start_backend()`. Stop it with `stop_backend()`. Do not run the notebook server and terminal server on the same port together.

## Workflow

1. Start a visit. Select any number of JPEG, PNG or WebP images for one record, in page order. You can add more images before analysis.
2. Analyze once: the frontend posts all files as repeated `images` multipart parts. OCR processes each photo and extraction reads the combined transcription.
3. Review the **accepted**, **review**, and **missing** groups. Evidence, reasons and clarification questions appear under each field.
4. Confirm candidates, type corrections for the LLM to interpret, or explicitly leave a field blank. Confirm each LLM-interpreted correction before saving. Accepted values can also be changed.
5. Confirm the complete record. The server exports `work/registry/registry.csv` with the original 31 columns. Repeated saves of the same record do not add duplicate rows.

Sessions and review evidence persist in `work/registry/sessions.sqlite3`. Reloading the same browser tab restores its record. Temporary uploaded images are removed after processing. Patient lookup is not implemented. The server is local-only, without authentication; configure authentication before any shared deployment.

## API

- `POST /api/extract`: multipart `images` (repeated); legacy `image` also supported. Returns `record_id`, `revision`, `page_count`, all `fields`, grouped `accepted`/`review`/`missing`, `message`, `ready_to_save`.
- `GET /api/records/<record_id>`: retrieve saved review state.
- `POST /api/records/<record_id>/review`: JSON `{"revision":0,"field":"age (years)","action":"modify","response":"28 ans"}`. Actions: `modify`, `confirm`, `missing`. Always use the revision returned by the latest response. Modified values need confirmation.
- `POST /api/records/<record_id>/finalize`: JSON `{"revision":32,"confirm":true}`. Refuses unresolved fields. Export is atomic and serialized; SQLite is authoritative, allowing failed CSV writes to be retried without duplicate rows. Close the CSV in Excel if Windows prevents replacing it.

## Configuration and limits

No fixed page-type or eight-photo limit. Configurable safeguards still apply: `MAX_UPLOAD_MB` (100), `MAX_FORM_PARTS` (10000), `OLLAMA_CONTEXT` (32768). Large dossiers can exceed the model context; increase it for your hardware. Requests are synchronous and can take minutes. Model calls time out after 300 seconds. Failed extraction creates no partial record. OCR output truncation is treated as an error.

Accepted means supported by model output and application checks, not independently verified clinical accuracy. The review screen is the final opportunity to inspect accepted values too. Text beginning with spreadsheet formula characters is escaped in CSV.

## Validate

```powershell
python backend/test_workflow.py
```

Tests use synthetic photos and mocked model replies, cover 12-photo uploads, routing, evidence checks, LLM correction confirmation, missing values, stale revisions, persistence, private file access and retry-safe CSV saving. Live model accuracy should be evaluated against labeled forms.

Ollama's image and structured-output interfaces follow its official documentation:
https://github.com/ollama/ollama/blob/main/docs/capabilities/vision.mdx
https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx

### Live processing feedback

The chat displays backend progress for preparation, OCR of each page, registry extraction and validation, plus elapsed time. Message input, Enter/send, uploads, review inputs and buttons are locked until the active request completes or fails. Corrections and CSV saves also display an in-chat processing state.

The frontend generates a random `progress_id` for each analysis, includes it in the multipart upload and polls `GET /api/progress/<progress_id>` for ordered `events`. Progress contains stage messages only and expires after 24 hours when another analysis starts.
