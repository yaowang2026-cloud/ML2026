from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path
from uuid import uuid4

from extraction import extract_image


# ============================================================
# PATHS
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

UPLOAD_FOLDER = PROJECT_ROOT / "work" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "message": "DayOne backend is running"
    })


# ============================================================
# IMAGE EXTRACTION
# ============================================================

@app.route("/api/extract", methods=["POST"])
def extract():

    # Make sure an image was sent
    if "image" not in request.files:
        return jsonify({
            "error": "Aucune image reçue."
        }), 400

    image = request.files["image"]

    if image.filename == "":
        return jsonify({
            "error": "Fichier invalide."
        }), 400

    # --------------------------------------------------------
    # Page type
    # --------------------------------------------------------

    page_type = request.form.get("page_type", "4")

    if page_type not in {
        "1", "2", "3", "4",
        "5", "6", "7", "8"
    }:
        return jsonify({
            "error": "page_type doit être entre 1 et 8."
        }), 400

    # --------------------------------------------------------
    # Save uploaded image
    # --------------------------------------------------------

    extension = Path(image.filename).suffix.lower()

    if extension not in {".jpg", ".jpeg", ".png"}:
        return jsonify({
            "error": "Format accepté: JPG, JPEG ou PNG."
        }), 400

    filename = f"{uuid4().hex}{extension}"

    image_path = UPLOAD_FOLDER / filename

    image.save(image_path)

    # --------------------------------------------------------
    # Run our extraction
    # --------------------------------------------------------

    try:

        result = extract_image(
            image_path,
            page_type=page_type
        )

        # Generate a temporary visit ID
        result["record_id"] = (
            f"VISIT-{uuid4().hex[:8].upper()}"
        )

        # Determine whether midwife review is needed
        needs_review = any(
            field["status"] in {
                "NEEDS_REVIEW",
                "ILLEGIBLE"
            }
            for field in result["fields"]
        )

        if needs_review:
            result["status"] = "NEEDS_REVIEW"
        else:
            result["status"] = "AI_PROCESSED"

        return jsonify(result)

    except Exception as error:

        app.logger.exception(
            "Erreur pendant l'extraction"
        )

        return jsonify({
            "error": str(error)
        }), 500


# ============================================================
# SERVE FRONTEND
# ============================================================

@app.route("/")
def index():
    return send_from_directory(
        PROJECT_ROOT,
        "index.html"
    )


@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(
        PROJECT_ROOT,
        filename
    )


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )