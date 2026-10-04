import csv
import unicodedata

PATIENTES_TEST = {"9", "10"}   # jamais utilisées pour apprendre les zones

def lire_csv(chemin):
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


corrige = [l for l in lire_csv("work/ground_truth.csv") if l["patient"] in PATIENTES_TEST]
predictions = {(l["pdf_page"], l["field_key"]): l for l in lire_csv("work/predictions.csv")}
identifiants = [l["value"] for l in lire_csv("work/pii_do_not_store.csv")]

def normaliser(texte):
    """'3626 g' et '3626g' -> '3626' ; 'Céphalique' et 'cephalique' -> 'cephalique'."""
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")  # enlève les accents
    texte = texte.lower().replace(",", ".").replace("—", "").strip()
    texte = " ".join(texte.split())                                       # espaces en trop
    for unite in (" g/dl", " g/l", " kg", " cm", " sa", " °c", " jours", " g"):
        if texte.endswith(unite):
            texte = texte[: -len(unite)]
    return texte.replace(" ", "")

details = []
for vrai in corrige:
    pred = predictions.get((vrai["pdf_page"], vrai["field_key"]),
                           {"value": "", "status": "MANQUANT", "confidence": "0"})

    if vrai["kind"] == "checkbox":
        categorie = "case à cocher"
        juste = pred["value"] == vrai["value"]

    elif normaliser(vrai["value"]) == "":
        categorie = "champ vide"
        juste = pred["value"].strip() == ""

    else:
        categorie = "champ rempli"
        juste = normaliser(pred["value"]) == normaliser(vrai["value"])
details.append({"page": vrai["pdf_page"], "champ": vrai["field_key"], "categorie": categorie,
                    "vraie_valeur": vrai["value"], "valeur_lue": pred["value"],
                    "statut": pred["status"], "confiance": float(pred["confidence"]),
                    "juste": juste})

def pourcentage(lignes):
    if len(lignes) == 0:
        return "aucun champ"
    return f"{100 * sum(l['juste'] for l in lignes) / len(lignes):5.1f} %  ({len(lignes)} champs)"

print("Champs du corrigé pour les patientes de test :", len(corrige))
print("Prédictions lues :", len(predictions))
print("Catégories trouvées :", {d["categorie"] for d in details})

print("=== 1. Exactitude (patientes 9 et 10) ===")
for categorie in ("champ rempli", "champ vide", "case à cocher"):
    lignes = [d for d in details if d["categorie"] == categorie]
    print(f"  {categorie:<15} {pourcentage(lignes)}")
print(f"  {'TOTAL':<15} {pourcentage(details)}")

print("\n=== 2. Le statut est-il fiable ? ===")
for statut in ("CONNU", "A_REVISER", "ILLISIBLE", "NON_FOURNI"):
    lignes = [d for d in details if d["statut"] == statut]
    if lignes:
        print(f"  {statut:<11} justes à {pourcentage(lignes)}")

print("\n=== 3. La confiance est-elle honnête ? ===")
print("  confiance      champs   confiance moyenne   vraiment justes")
for bas in (0.0, 0.2, 0.4, 0.6, 0.8):
    haut = bas + 0.2
    lignes = [d for d in details if bas <= d["confiance"] < haut or (haut == 1.0 and d["confiance"] == 1.0)]
    if lignes:
        moyenne = sum(d["confiance"] for d in lignes) / len(lignes)
        justes = sum(d["juste"] for d in lignes) / len(lignes)
        print(f"  {bas:.1f} à {haut:.1f}   {len(lignes):6d}        {moyenne:.2f}               {justes:.2f}")

print("\n=== 4. Confidentialité ===")
fuites = [d for d in details
          if any(len(i) >= 4 and normaliser(i) in normaliser(d["valeur_lue"]) for i in identifiants)]
print(f"  Identifiants retrouvés dans les résultats : {len(fuites)}")

with open("work/evaluation.csv", "w", newline="", encoding="utf-8") as f:
    ecrivain = csv.DictWriter(f, fieldnames=list(details[0]))
    ecrivain.writeheader()
    ecrivain.writerows(details)
print("\nDétail champ par champ : work/evaluation.csv")