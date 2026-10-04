# DayOne: multi-photo registry extraction

The frontend and notebook share the same local Ollama backend. The original files are in `original-backup/`.

## Start the backend (Windows / VS Code)

Open this project folder in VS Code, then open **Terminal > New Terminal** (PowerShell).
Use Python 3.10 or newer. Run these commands from the project folder:

```powershell
cd 'C:\Users\wycwi\OneDrive\Desktop\ML2026-feature-multi-image-interface'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe backend/app.py
```

For later launches, only the last command is needed. Using the explicit virtual-environment Python path avoids PowerShell activation-policy issues. Keep the terminal running and open [DayOne](http://127.0.0.1:5001/). Stop the backend with **Ctrl+C**. If port 5001 is already in use, stop the existing backend before starting another.

Choose one model setup below: **Local** uses Ollama; **OpenAI** uses your API key. Both use the same Python backend. Opening the HTML alone does not run extraction.

Alternatively, open the modified `granite42_ollama_maternal_extraction_example-2.ipynb`, run its setup cells, then call `start_backend()`. Stop it with `stop_backend()`. Do not run the notebook server and terminal server on the same port together.

## Install the local LLM with Ollama

1. Download and install [Ollama for Windows](https://ollama.com/download/windows). Start the Ollama app, then reopen the VS Code terminal so the `ollama` command is available.
2. Check the installation and download the project's default vision model:

   ```powershell
   ollama --version
   ollama pull qwen3.5:9b
   ollama list
   ```

3. Optional: test the model in the terminal:

   ```powershell
   ollama run qwen3.5:9b
   ```

   Type a short message, then `/bye` to leave the model chat. The application sends photos through Ollama's API; you do not need to keep this interactive chat open.
4. Keep the Ollama app running. Check its local API:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:11434/api/tags
   ```

   If Ollama is not already running, start `ollama serve` in a separate terminal and leave it open. Do not start a second server if the Ollama app already serves port 11434.
5. Start the DayOne backend using the instructions above. In the interface, select **Local**, choose one patient's photos, and analyze.

The initial model download requires internet access; local inference runs on your computer. The [official qwen3.5 model listing](https://ollama.com/library/qwen3.5) lists `qwen3.5:9b` as a text-and-image model with a roughly 6.6 GB download. Allow additional disk space and RAM/VRAM for execution and context; download size is not total runtime memory usage.

The app defaults to `qwen3.5:9b` and a 32768-token context setting. To explicitly set these before starting the backend:

```powershell
$env:OLLAMA_MODEL = 'qwen3.5:9b'
$env:OLLAMA_CONTEXT = '32768'
.\.venv\Scripts\python.exe backend/app.py
```

Use a model with image input and structured-output support if changing `OLLAMA_MODEL`; pull its exact tag first. Larger context settings require more memory. If `ollama` is not recognized, reopen the terminal after installation. If the backend cannot connect, check the Ollama app/API above. If the model is missing, repeat `ollama pull qwen3.5:9b`. If inference runs out of memory or times out, check available memory and model size before increasing context.

Official references: [Ollama on Windows](https://docs.ollama.com/windows), [CLI commands](https://docs.ollama.com/cli).

## Workflow

1. Start a visit. Select all JPEG, PNG or WebP images for one patient in a single batch. Each new selection replaces the previous batch.
2. Analyze once: the frontend posts all files as repeated `images` multipart parts. OCR processes each photo and extraction reads the combined transcription.
3. Confirm the mandatory patient ID first, then review the **accepted**, **review**, and **missing** groups. Evidence, reasons and clarification questions appear under each field.
4. Confirm candidates, type corrections for the LLM to interpret, or explicitly leave a field blank. Confirm each LLM-interpreted correction before saving. Accepted values do not need individual confirmation; use **Modify** if a value needs correction.
5. When the patient ID is confirmed and no fields remain unresolved, the record automatically moves to **Saved records**. The server exports `work/registry/registry.csv` with the original 31 columns. Repeated saves of the same record do not add duplicate rows.

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

## Optional OpenAI online mode

The header **Local / OpenAI** button selects the provider for the next photo batch. Local remains the default. Existing records retain their original provider for AI corrections, even if you switch the button for the next batch.

### Where the API key is stored

The private configuration file is **`backend/openai-config.ini`**.
On this computer, its full path is:

```text
C:\Users\wycwi\OneDrive\Desktop\ML2026-feature-multi-image-interface\backend\openai-config.ini
```

This is a plain-text file read by the Python backend. It is excluded from Git and is not served to the browser. Because this project lives under OneDrive, it may still be synced by OneDrive; Git exclusion does not prevent cloud sync. Do not share the file or include it in project archives.

### Configure the OpenAI API key in the file

1. In VS Code, open `backend/openai-config.ini`. If the file is missing, copy the blank template without overwriting any existing configuration:

   ```powershell
   if (-not (Test-Path backend/openai-config.ini)) {
       Copy-Item backend/openai-config.example.ini backend/openai-config.ini
   }
   ```

2. Enter your own OpenAI API key and model:

   ```ini
   [openai]
   api_key = paste-your-api-key-here
   model = gpt-4.1-mini
   ```

3. Replace the placeholder with the real key, without surrounding quotes, and save the file. Do not paste your key into chat or put it in `app.js` or `index.html`.
4. Start the backend, open [DayOne](http://127.0.0.1:5001/), and click the **Local / OpenAI** button until it says **OpenAI**. Analyze a new photo batch. Ollama does not need to be running for this mode.

File values take priority over `OPENAI_API_KEY` and `OPENAI_MODEL` environment variables. Blank file values fall back to those environment variables, then to `gpt-4.1-mini` for the model. File edits load automatically on new calls; changing the model applies to new records, while existing records retain their originally selected model.

If OpenAI reports a missing key, check the file path, `[openai]` section and `api_key` entry. HTTP 401 indicates a key problem; HTTP 429 calls for checking API quota/rate limits. API usage is billed to the API account, so it needs usable quota. No key is needed in Local mode.

`gpt-4.1-mini` is the default online model. Overrides must support image input, temperature 0, and structured JSON output. No extra Python dependency is needed. Online mode sends the selected photos, extracted text and AI corrections to OpenAI; API usage is billed to the configured API account. The API key is only read by the backend.

Both modes run the same per-page OCR, 31-field extraction, evidence/type validation, accepted/review/missing workflow, user confirmation, and CSV saving. Original prompts, local Ollama model/options, page/context safeguards, and UI controls are preserved. OpenAI receives the same temperature and output-token limits where available; Ollama-only `num_ctx`, `think` and `keep_alive` settings are not API parameters. Different models can produce different results. Online errors are shown without silently switching providers. Requests set `store=false`.

API clients can send multipart `provider=local` or `provider=openai` to `/api/extract`; omitted means local. The returned record includes `model_provider` and `model_name`.

Provider checks: `python -m unittest backend.test_model_provider` (mocked API, no paid requests).

Official API documentation: [image inputs](https://developers.openai.com/api/docs/guides/images-vision), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
