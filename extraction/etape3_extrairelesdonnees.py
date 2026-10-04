import csv
import os
from pathlib import Path
import cv2
import pytesseract
from pathlib import os 

# ------------------------------------------------------------------
# PARTIE 1 : apprendre où se trouve chaque champ sur la page
# ------------------------------------------------------------------
PATIENTES_ENTRAINEMENT = {"1", "2", "3", "4", "5", "6", "7", "8"}  # 9 et 10 gardées pour le test

# Lire le corrigé produit à l'étape 2
with open("work/ground_truth.csv", encoding="utf-8") as f:
    corrige = list(csv.DictReader(f))

# Pour chaque champ, le rectangle qui englobe toutes les positions vues
zones = {}
for ligne in corrige:
    if ligne["patient"] not in PATIENTES_ENTRAINEMENT:
        continue                      # on ne regarde jamais les patientes de test
    if ligne["x0"] == "":
        continue                      # champ vide : pas de position
    champ = (ligne["page_type"], ligne["field_key"])
    x0, y0 = float(ligne["x0"]), float(ligne["y0"])
    x1, y1 = float(ligne["x1"]), float(ligne["y1"])
    if champ in zones:
        ancien = zones[champ]
        zones[champ] = (min(ancien[0], x0), min(ancien[1], y0),
                        max(ancien[2], x1), max(ancien[3], y1))
    else:
        zones[champ] = (x0, y0, x1, y1)

print(len(zones), "zones apprises sur les patientes 1 à 8")
print("Exemple, l'âge :", zones[("2", "identification_antecedents > Age")])


# ------------------------------------------------------------------
# PARTIE 2 : lire une image mot par mot avec Tesseract
# ------------------------------------------------------------------
LANGUE = "fra"

# Dire à Python où se trouve Tesseract (Windows)
CHEMIN_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(CHEMIN_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = CHEMIN_TESSERACT


def preparer(image):
    """Noir et blanc : le fond rose devient blanc, l'encre devient noire."""
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, noir_et_blanc = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return noir_et_blanc


def lire_page(noir_et_blanc):
    """Renvoie la liste des mots lus, avec leur position (en fraction) et leur confiance."""
    hauteur, largeur = noir_et_blanc.shape
    donnees = pytesseract.image_to_data(noir_et_blanc, lang=LANGUE, config="--psm 11",
                                        output_type=pytesseract.Output.DICT)
    mots = []
    for i in range(len(donnees["text"])):
        texte = donnees["text"][i].strip()
        confiance = float(donnees["conf"][i])
        if texte == "" or confiance < 0:
            continue                  # case vide ou bloc sans texte
        gauche, haut = donnees["left"][i], donnees["top"][i]
        largeur_mot, hauteur_mot = donnees["width"][i], donnees["height"][i]
        mots.append({
            "texte": texte,
            "x": gauche / largeur,                              # bord gauche
            "cx": (gauche + largeur_mot / 2) / largeur,         # centre, horizontal
            "cy": (haut + hauteur_mot / 2) / hauteur,           # centre, vertical
            "confiance": confiance / 100,                       # 0 à 1
        })
    return mots

SEUIL_CONNU = 0.85   # confiance minimale pour dire CONNU (sinon A_REVISER)
SEUIL_ENCRE = 0.03   # part d'encre au-dessus de laquelle « quelque chose est écrit »
SEUIL_CASE = 0.24    # part d'encre au-dessus de laquelle une case est cochée

def zone_mots(zone):
    """Zone élargie pour ramasser les mots (une écriture peut déborder un peu)."""
    x0, y0, x1, y1 = zone
    return (x0 - 0.004, y0 - 0.003, x1 + 0.03, y1 + 0.003)

def zone_encre(zone, kind):
    """Zone resserrée pour mesurer l'encre, sans toucher les traits du formulaire."""
    x0, y0, x1, y1 = zone
    if kind == "checkbox":   # l'intérieur de la case, sans son contour
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return (cx - 0.006, cy - 0.004, cx + 0.006, cy + 0.004)
    marge = (y1 - y0) * 0.2  # on retire 20 % en haut et en bas (lignes du tableau)
    return (x0 + 0.002, y0 + marge, x1 + 0.01, y1 - marge)

def part_encre(noir_et_blanc, zone):
    """Proportion de pixels noirs dans la zone : 0 = vide, 1 = tout noir."""
    hauteur, largeur = noir_et_blanc.shape
    x0, y0, x1, y1 = zone
    morceau = noir_et_blanc[int(y0 * hauteur):int(y1 * hauteur), int(x0 * largeur):int(x1 * largeur)]
    if morceau.size == 0:
        return 0.0
    return float((morceau < 128).mean())

def lire_champ_texte(mots, noir_et_blanc, zone):
    """Valeur, statut et confiance d'un champ écrit."""
    x0, y0, x1, y1 = zone_mots(zone)
    dedans = [m for m in mots if x0 <= m["cx"] <= x1 and y0 <= m["cy"] <= y1]

    if dedans:
        dedans.sort(key=lambda m: (round(m["cy"], 2), m["x"]))   # ordre de lecture
        valeur = " ".join(m["texte"] for m in dedans)
        confiance = min(m["confiance"] for m in dedans)         # le mot le plus douteux décide
        statut = "CONNU" if confiance >= SEUIL_CONNU else "A_REVISER"
        return valeur, statut, round(confiance, 2)
    if part_encre(noir_et_blanc, zone_encre(zone, "text")) > SEUIL_ENCRE:
        return "", "ILLISIBLE", 0.2      # de l'encre, mais aucun mot lisible
    return "", "NON_FOURNI", 0.9         # zone blanche : rien d'écrit
def lire_case(noir_et_blanc, zone):
    """Valeur, statut et confiance d'une case à cocher."""
    encre = part_encre(noir_et_blanc, zone_encre(zone, "checkbox"))
    valeur = "COCHÉ" if encre > SEUIL_CASE else "NON_COCHÉ"
    ecart = abs(encre - SEUIL_CASE) / SEUIL_CASE     # loin du seuil = on est sûr
    confiance = round(min(0.5 + 0.5 * ecart, 1.0), 2)
    statut = "CONNU" if confiance >= SEUIL_CONNU else "A_REVISER"
    return valeur, statut, confiance
champs_par_type = {}
for ligne in corrige:
    champs_par_type.setdefault(ligne["page_type"], set()).add((ligne["field_key"], ligne["kind"]))

DOSSIER_IMAGES = Path("work/data/Paper Registry")
images = {}
for fichier in sorted(DOSSIER_IMAGES.glob("dossiers_specimen_10_patientes-*.png")):
    numero = int(fichier.stem.split("-")[1][:2])
    images.setdefault(numero, fichier)
resultats = []
for numero, fichier in sorted(images.items()):
    type_page = str((numero - 1) % 8 + 1)
    noir_et_blanc = preparer(cv2.imread(str(fichier)))
    mots = lire_page(noir_et_blanc)

    for champ, kind in sorted(champs_par_type[type_page]):
        zone = zones.get((type_page, champ))
        if zone is None:
            valeur, statut, confiance = "", "A_REVISER", 0.1
        elif kind == "checkbox":
            valeur, statut, confiance = lire_case(noir_et_blanc, zone)
        else:
            valeur, statut, confiance = lire_champ_texte(mots, noir_et_blanc, zone)

        resultats.append({"pdf_page": numero, "field_key": champ, "value": valeur,
                          "status": statut, "confidence": confiance})
        print(f"Page {numero}/80 lue", end="\r", flush=True)

with open("work/predictions.csv", "w", newline="", encoding="utf-8") as f:
    ecrivain = csv.DictWriter(f, fieldnames=["pdf_page", "field_key", "value", "status", "confidence"])
    ecrivain.writeheader()
    ecrivain.writerows(resultats)
print()
print(len(resultats), "champs extraits, enregistrés dans work/predictions.csv")