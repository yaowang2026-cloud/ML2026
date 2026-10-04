import csv
from pathlib import Path

import cv2
import easyocr


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GROUND_TRUTH = PROJECT_ROOT / "work" / "ground_truth.csv"


# ============================================================
# SETTINGS FROM TEAMMATE'S EXTRACTION
# ============================================================

TRAIN_PATIENTS = {str(i) for i in range(1, 9)}

SEUIL_CONNU = 0.85
SEUIL_ENCRE = 0.03
SEUIL_CASE = 0.24

# EasyOCR replaces pytesseract.
# First run may download the OCR models.
reader = easyocr.Reader(["fr", "en"], gpu=False)


# ============================================================
# LOAD TRAINING DATA
# ============================================================

def load_ground_truth():
    if not GROUND_TRUTH.exists():
        raise FileNotFoundError(
            f"ground_truth.csv introuvable: {GROUND_TRUTH}"
        )

    with open(GROUND_TRUTH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ============================================================
# LEARN FIELD POSITIONS
# ============================================================

def learn_zones(corrige):
    zones_apprises = {}

    for ligne in corrige:
        if ligne["patient"] not in TRAIN_PATIENTS:
            continue

        cle = (ligne["page_type"], ligne["field_key"])

        try:
            coords = (
                float(ligne["x0"]),
                float(ligne["y0"]),
                float(ligne["x1"]),
                float(ligne["y1"]),
            )
        except (ValueError, KeyError):
            continue

        zones_apprises.setdefault(cle, []).append(coords)

    zones = {}

    for cle, liste in zones_apprises.items():
        zones[cle] = tuple(
            sum(coord[i] for coord in liste) / len(liste)
            for i in range(4)
        )

    return zones


# ============================================================
# IMAGE PREPARATION
# ============================================================

def preparer(image):
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, noir_et_blanc = cv2.threshold(
        gris,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    return noir_et_blanc


# ============================================================
# EASYOCR
# ============================================================

def lire_page(image):
    """
    Returns OCR words in a format similar to the teammate's
    original pytesseract pipeline.
    """

    resultats = reader.readtext(image)

    mots = []

    for boite, texte, confiance in resultats:
        if not texte.strip():
            continue

        xs = [point[0] for point in boite]
        ys = [point[1] for point in boite]

        mots.append({
            "text": texte.strip(),
            "conf": float(confiance),
            "left": int(min(xs)),
            "top": int(min(ys)),
            "width": int(max(xs) - min(xs)),
            "height": int(max(ys) - min(ys)),
        })

    return mots


# ============================================================
# ZONE HELPERS
# ============================================================

def zone_mots(mots, zone, largeur, hauteur):
    x0, y0, x1, y1 = zone

    x0 *= largeur
    x1 *= largeur
    y0 *= hauteur
    y1 *= hauteur

    trouves = []

    for mot in mots:
        centre_x = mot["left"] + mot["width"] / 2
        centre_y = mot["top"] + mot["height"] / 2

        if x0 <= centre_x <= x1 and y0 <= centre_y <= y1:
            trouves.append(mot)

    trouves.sort(key=lambda m: (m["top"], m["left"]))

    return trouves


def part_encre(noir_et_blanc, zone):
    hauteur, largeur = noir_et_blanc.shape[:2]

    x0, y0, x1, y1 = zone

    x0 = max(0, int(x0 * largeur))
    x1 = min(largeur, int(x1 * largeur))
    y0 = max(0, int(y0 * hauteur))
    y1 = min(hauteur, int(y1 * hauteur))

    region = noir_et_blanc[y0:y1, x0:x1]

    if region.size == 0:
        return 0.0

    pixels_noirs = (region < 128).sum()

    return float(pixels_noirs / region.size)


# ============================================================
# TEXT FIELD
# ============================================================

def lire_champ_texte(mots, noir_et_blanc, zone):
    hauteur, largeur = noir_et_blanc.shape[:2]

    trouves = zone_mots(
        mots,
        zone,
        largeur,
        hauteur
    )

    encre = part_encre(noir_et_blanc, zone)

    if not trouves:
        if encre < SEUIL_ENCRE:
            return "", "NOT_PROVIDED", 0.95

        return "", "ILLEGIBLE", 0.25

    valeur = " ".join(m["text"] for m in trouves)

    confiance = sum(
        m["conf"] for m in trouves
    ) / len(trouves)

    confiance = round(float(confiance), 3)

    if confiance >= SEUIL_CONNU:
        statut = "KNOWN"
    else:
        statut = "NEEDS_REVIEW"

    return valeur, statut, confiance


# ============================================================
# CHECKBOX FIELD
# ============================================================

def lire_case(noir_et_blanc, zone):
    encre = part_encre(noir_et_blanc, zone)

    if encre >= SEUIL_CASE:
        return "CHECKED", "KNOWN", min(round(encre, 3), 1.0)

    return "UNCHECKED", "KNOWN", round(1.0 - encre, 3)


# ============================================================
# MAIN FUNCTION USED BY FLASK
# ============================================================

def extract_image(image_path, page_type="4"):

    corrige = load_ground_truth()
    zones = learn_zones(corrige)

    champs = {}

    for ligne in corrige:
        if ligne["page_type"] == str(page_type):
            champs[ligne["field_key"]] = ligne["kind"]

    if not champs:
        raise ValueError(
            f"Aucun champ trouvé pour page_type={page_type}"
        )

    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError(
            f"Impossible de lire l'image: {image_path}"
        )

    noir_et_blanc = preparer(image)

    # Real OCR
    mots = lire_page(noir_et_blanc)

    fields = []

    for champ, kind in sorted(champs.items()):

        zone = zones.get(
            (str(page_type), champ)
        )

        if zone is None:

            valeur = ""
            statut = "NEEDS_REVIEW"
            confiance = 0.10

        elif kind == "checkbox":

            valeur, statut, confiance = lire_case(
                noir_et_blanc,
                zone
            )

        else:

            valeur, statut, confiance = lire_champ_texte(
                mots,
                noir_et_blanc,
                zone
            )

        fields.append({
            "name": champ,
            "label": champ.split(">")[-1].strip(),
            "value": valeur,
            "status": statut,
            "confidence": confiance
        })

    return {
        "page_type": str(page_type),
        "fields": fields
    }