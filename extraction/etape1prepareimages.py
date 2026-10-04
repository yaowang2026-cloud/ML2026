import hashlib
import json
import zipfile
from pathlib import Path

ARCHIVE = "dayone-participants.zip"
DOSSIER = Path("work")

# 1. Décompresser l'archive dans le dossier "work"
with zipfile.ZipFile(ARCHIVE) as z:
        z.extractall(DOSSIER)
print("Archive décompressée dans", DOSSIER)

# 2. vérifier que les fichiers ne sont pas abîmés
manifest = json.loads((DOSSIER / "manifest.json").read_text(encoding="utf-8"))
corrompus = 0
for f in manifest["files"]:
        contenu = (DOSSIER / f["path"]).read_bytes()
        if hashlib.sha256(contenu).hexdigest() != f["sha256"]:
                corrompus += 1
        print("Fichier corrompu :", f["path"])
print(len(manifest["files"]), "fichiers vérifiés,", corrompus, "corrompus")

# 3. compter les images en double
empreintes = [f["sha256"] for f in manifest["files"] if f["path"].endswith((".png", ".jpg"))]
print(len(empreintes), "images, dont", len(set(empreintes)), "uniques")
