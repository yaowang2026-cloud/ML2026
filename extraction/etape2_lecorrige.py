import csv, re, sys
from pathlib import Path
import pdfplumber

# 2. les réglages
PDF = "data/Paper Registry/dossiers_specimen_10_patientes.pdf"
FORM_INK = (0.12, 0.08, 0.1) # couleur des traits du formulaire ; tout autre trait = stylo
PII_LABELS = re.compile(r"^(nom( du mari)?|nom/pr[ée]nom.*|.*parturiente|cin|adresse|t[ée]l[ée]phone|patiente)$", re.I)
IGNORE = re.compile(r"(SPÉCIMEN|Patiente fictive|Document synthétique|Modèle de formulaire)")

# 3.transformer des mots isolés en morceaux de texte
def segments(page, breaks=()):
    words = page.extract_words(extra_attrs=["fontname"], keep_blank_chars=False)
    for w in words:
        w["hand"] = "Helvetica" not in w["fontname"] # 5 polices manuscrites (Caveat, Gaegu…)
        w["bold"] = "Bold" in w["fontname"]
        w["yc"] = (w["top"] + w["bottom"]) / 2
    words.sort(key=lambda w: w["yc"])
    lines = []
    for w in words:
        if lines and abs(lines[-1][-1]["yc"] - w["yc"]) < 5:
            lines[-1].append(w)
        else:
            lines.append([w])
    segs = []
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        for w in line:
            s = segs[-1] if segs else None
            max_gap = 6 if w["hand"] else 9
            at_column = w["hand"] and any(abs(w["x0"] - b) < 4 for b in breaks)
            if (s and s["line"] is line and s["hand"] == w["hand"] and not at_column 
                    and 0 <= w["x0"] - s["x1"] < max_gap):
                s["text"] += " " + w["text"]; s["x1"] = w["x1"]
                s["bottom"] = max(s["bottom"], w["bottom"]); s["top"] = min(s["top"], w["top"])
            else:
                segs.append({**{k: w[k] for k in ("text", "x0", "x1", "top", "bottom", "yc", "hand", "bold")},
                             "line": line})    
    return [s for s in segs if not IGNORE.search(s["text"])] 