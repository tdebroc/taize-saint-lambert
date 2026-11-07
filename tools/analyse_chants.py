#!/usr/bin/env python3
"""Analyse des chants des prières Taizé de Saint-Lambert.

1. Liste les chants des carnets (PDF du dossier `carnet chants/`).
2. Relève les chants utilisés dans chaque prière (`site/prieres/AAAA-MM-JJ.html`).
3. Génère un Excel où l'on peut inclure / exclure des prières (ex. les plus
   anciennes) : le classement par nombre d'occurrences se recalcule tout seul.

Usage (depuis la racine du dépôt) :
    python3 tools/analyse_chants.py
    python3 tools/analyse_chants.py --depuis 2026-09-01   # exclut d'office les prières plus anciennes
    python3 tools/analyse_chants.py -o mon_fichier.xlsx

Prérequis : `pip install openpyxl` et `pdftotext` (poppler, `brew install poppler`).
Pour ajouter une prière : déposer son HTML dans `site/prieres/` et relancer.
"""
import argparse
import datetime as dt
import re
import subprocess
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
CARNET_PRINCIPAL = "Carnet de Chant pour la priere Paris Taize  (1).pdf"
CARNET_BONUS = "Taizé - Carnet Bonus Saint Lambert v1.pdf"
LABEL_PRINCIPAL = "Carnet"
LABEL_BONUS = "Carnet Bonus"

# Les pages du site écrivent parfois un chant autrement que le carnet.
# Clé et valeur sont des titres normalisés (voir `cle`) ; la valeur doit être la clé du carnet.
ALIASES = {
    "kyrie": "kyrie 21",
    "kyrie eleison": "kyrie 21",
    "v tebi je izvir": "v tebi je izvir zivljenja",
}

# Les numéros du carnet principal sont écrits avec des glyphes privés (U+F430 + chiffre).
PUA_DIGITS = {chr(0xF430 + d): str(d) for d in range(10)}

FONT = "Arial"


def cle(titre):
    """Titre normalisé : sans accents, ponctuation ni casse (pour rapprocher les variantes)."""
    t = unicodedata.normalize("NFKD", titre.replace("’", "'"))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def canonique(titre):
    k = cle(titre)
    return ALIASES.get(k, k)


# --------------------------------------------------------------------------- carnets

def pdf_text(path):
    try:
        out = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True,
                             capture_output=True, text=True).stdout
    except FileNotFoundError:
        sys.exit("pdftotext introuvable : brew install poppler")
    for glyph, digit in PUA_DIGITS.items():
        out = out.replace(glyph, digit)
    return out


def lire_carnet_principal(path):
    """Titres du type « 14. Behüte mich, Gott » (un par ligne de titre)."""
    chants, vus = [], set()
    for ligne in pdf_text(path).splitlines():
        m = re.match(r"^\s*(\d+)\.\s+(\S.*?)(?:\s{2,}.*)?$", ligne)
        # un numéro déjà vu = couplet « 1. 2. 3. » d'un chant, pas un titre
        if m and len(m.group(2)) < 60 and m.group(1) not in vus:
            vus.add(m.group(1))
            chants.append((m.group(1), m.group(2).strip()))
    return chants


def lire_carnet_bonus(path):
    """Table des matières du carnet bonus : « 18   Confitemini Domino » (numéro parfois absent)."""
    chants = []
    for ligne in pdf_text(path).splitlines():
        s = ligne.strip()
        if len(s) < 4 or "Carnet Bonus" in s:
            continue
        m = re.match(r"^(\d+)?\s*(\D\S.*)$", s)
        if m:
            chants.append((m.group(1) or "", m.group(2).strip()))
    return chants


# --------------------------------------------------------------------------- prières

class PriereParser(HTMLParser):
    """Relève chaque <span class="chant"> avec son numéro, son titre et sa section (<h2>)."""

    def __init__(self):
        super().__init__()
        self.section = ""
        self.chants = []  # (section, numéro, titre)
        self._in_h2 = False
        self._h2_parts = []
        self._depth = 0          # profondeur de span.chant (0 = hors chant)
        self._in_num = False
        self._in_link = False
        self._num = ""
        self._titre = ""
        self._section_chant = ""

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        if tag == "h2":
            self._in_h2, self._h2_parts = True, []
        elif tag == "span" and self._depth == 0 and "chant" in cls.split():
            self._depth = 1
            self._num = self._titre = ""
            self._section_chant = self.section
        elif self._depth:
            if tag == "span":
                self._depth += 1
                self._in_num = "num" in cls.split()
            elif tag == "a":
                self._in_link = True

    def handle_endtag(self, tag):
        if tag == "h2":
            self._in_h2 = False
            self.section = " ".join("".join(self._h2_parts).split())
        elif self._depth and tag == "a":
            self._in_link = False
        elif self._depth and tag == "span":
            self._depth -= 1
            self._in_num = False
            if self._depth == 0:
                self.chants.append((self._section_chant, self._num.strip(), " ".join(self._titre.split())))

    def handle_data(self, data):
        if self._in_h2 and not self._depth:
            self._h2_parts.append(data)
        elif self._depth and not self._in_link:
            if self._in_num:
                self._num += data
            else:
                self._titre += data


def section_nette(h2):
    """« ♪ Chants d'ouverture » -> « Chants d'ouverture » ; retire aussi le chant collé au titre."""
    h2 = h2.split("·")[0] if "Intentions" in h2 else h2
    return re.sub(r"^[^\w]+", "", h2).strip()


def lire_prieres(dossier):
    prieres = []
    for f in sorted(dossier.glob("*.html")):
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", f.stem)
        if not m:
            continue
        p = PriereParser()
        p.feed(f.read_text(encoding="utf-8"))
        prieres.append({
            "date": dt.date(*map(int, m.groups())),
            "fichier": f.name,
            "chants": [(section_nette(s), n, t) for s, n, t in p.chants],
        })
    return prieres


# --------------------------------------------------------------------------- fusion

def construire_catalogue(carnets, prieres):
    """Un chant = une clé de titre. Retourne {clé: {titre, carnets: [(label, num)], en_carnet}}."""
    cat = {}
    for label, chants in carnets:
        for num, titre in chants:
            noms = [titre] + [p for p in titre.split(" / ")]  # « A / B » : on reconnaît aussi A et B
            k = canonique(titre.split(" / ")[0]) if " / " in titre else canonique(titre)
            e = cat.setdefault(k, {"titre": titre.split(" / ")[0].strip(), "carnets": [], "en_carnet": True})
            e["carnets"].append((label, num))
            for n in noms[1:]:
                ALIASES.setdefault(cle(n), k)
    for pr in prieres:
        for _, num, titre in pr["chants"]:
            k = canonique(titre)
            if k not in cat:
                cat[k] = {"titre": titre, "carnets": [], "en_carnet": False}
    return cat


# --------------------------------------------------------------------------- Excel

def style_entete(cell, fill="3B3B3B"):
    cell.font = Font(name=FONT, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", start_color=fill)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def ecrire_excel(chemin, cat, prieres, depuis):
    wb = Workbook()
    thin = Side(style="thin", color="D0D0D0")
    bord = Border(left=thin, right=thin, top=thin, bottom=thin)
    base = Font(name=FONT)

    # --- données : occurrences[clé][index prière] = nombre
    occ = {k: [0] * len(prieres) for k in cat}
    for i, pr in enumerate(prieres):
        for _, _, titre in pr["chants"]:
            occ[canonique(titre)][i] += 1
    ordre = sorted(cat, key=lambda k: (-sum(occ[k]), cat[k]["titre"].lower()))

    # ============ feuille Analyse ============
    ws = wb.active
    ws.title = "Analyse"
    n_p, n_c = len(prieres), len(ordre)
    col0 = 8  # première colonne de prière (H)
    r_flag, r_head, r_first = 5, 6, 7
    r_last = r_first + n_c - 1
    c_last = col0 + n_p - 1
    L = get_column_letter
    pc1, pcn = L(col0), L(c_last)

    ws["A1"] = "Chants des prières Taizé – Saint-Lambert"
    ws["A1"].font = Font(name=FONT, bold=True, size=14)
    ws["A2"] = ("Pour ne compter que certaines prières : mettez 1 (incluse) ou 0 (exclue) dans la ligne "
                "« Inclure » au-dessus de chaque date. Occurrences, rang et onglet « Classement » se recalculent.")
    ws["A3"] = "Cases jaunes = à modifier. Pour ajouter une prière : déposer son HTML dans site/prieres/ et relancer tools/analyse_chants.py."
    for a in ("A2", "A3"):
        ws[a].font = Font(name=FONT, italic=True, color="555555")

    ws.cell(r_flag, col0 - 1, "Inclure (1/0) →").font = Font(name=FONT, bold=True)
    ws.cell(r_flag, col0 - 1).alignment = Alignment(horizontal="right")
    dv = DataValidation(type="list", formula1='"0,1"', allow_blank=False)
    ws.add_data_validation(dv)
    for j, pr in enumerate(prieres):
        c = col0 + j
        flag = ws.cell(r_flag, c, 0 if depuis and pr["date"] < depuis else 1)
        flag.font = Font(name=FONT, bold=True, color="0000FF")
        flag.fill = PatternFill("solid", start_color="FFFF00")
        flag.alignment = Alignment(horizontal="center")
        flag.border = bord
        dv.add(flag)
        h = ws.cell(r_head, c, pr["date"])
        h.number_format = "dd/mm/yyyy"
        style_entete(h, "8A4B08")
    ws.cell(4, col0, "Nombre de prières incluses :").font = base
    ws.cell(4, col0 + 3, f"=SUM({pc1}{r_flag}:{pcn}{r_flag})").font = Font(name=FONT, bold=True)

    for i, t in enumerate(["Chant", "Carnet(s) · n°", "Dans un carnet ?", "Occurrences",
                           "Rang", "Dernière utilisation", "Statut"], start=1):
        style_entete(ws.cell(r_head, i, t))
    ws.row_dimensions[r_head].height = 32

    flags = f"${pc1}${r_flag}:${pcn}${r_flag}"
    dates = f"${pc1}${r_head}:${pcn}${r_head}"
    for i, k in enumerate(ordre):
        r = r_first + i
        e = cat[k]
        carnets = " · ".join(f"{lab} {num}".strip() for lab, num in e["carnets"]) or "—"
        ws.cell(r, 1, e["titre"])
        ws.cell(r, 2, carnets)
        ws.cell(r, 3, "Oui" if e["en_carnet"] else "Non")
        row = f"${pc1}{r}:${pcn}{r}"
        ws.cell(r, 4, f"=SUMPRODUCT({flags},{row})")
        ws.cell(r, 5, f"=RANK(D{r},$D${r_first}:$D${r_last},0)+COUNTIF($D${r_first}:D{r},D{r})-1")
        ws.cell(r, 6, f'=IF(D{r}=0,"",_xlfn.MAXIFS({dates},{row},">0",{flags},1))').number_format = "dd/mm/yyyy"
        ws.cell(r, 7, f'=IF(D{r}=0,"Jamais (sur la sélection)",IF(D{r}=1,"1 fois",D{r}&" fois"))')
        for j in range(n_p):
            ws.cell(r, col0 + j, occ[k][j] or None).alignment = Alignment(horizontal="center")
        for c in range(1, c_last + 1):
            cell = ws.cell(r, c)
            cell.font = Font(name=FONT, bold=(c == 4))
            cell.border = bord
            if c in (3, 4, 5, 6):
                cell.alignment = Alignment(horizontal="center")
    ws.conditional_formatting.add(f"D{r_first}:D{r_last}",
                                  DataBarRule(start_type="num", start_value=0, end_type="max", color="F5871F"))
    for c, w in zip("ABCDEFG", (38, 26, 14, 13, 8, 18, 24)):
        ws.column_dimensions[c].width = w
    for j in range(n_p):
        ws.column_dimensions[L(col0 + j)].width = 13
    ws.freeze_panes = ws.cell(r_first, col0)
    ws.auto_filter.ref = f"A{r_head}:{pcn}{r_last}"

    # ============ feuille Classement (triée dynamiquement par rang) ============
    wc = wb.create_sheet("Classement")
    wc["A1"] = "Classement des chants (sur les prières incluses dans l'onglet Analyse)"
    wc["A1"].font = Font(name=FONT, bold=True, size=14)
    for i, t in enumerate(["Rang", "Chant", "Carnet(s) · n°", "Occurrences", "Dernière utilisation"], start=1):
        style_entete(wc.cell(3, i, t))
    rg = f"Analyse!$E${r_first}:$E${r_last}"
    for i in range(n_c):
        r = 4 + i
        wc.cell(r, 1, i + 1)
        for col, src in ((2, "A"), (3, "B"), (4, "D"), (5, "F")):
            rng = f"Analyse!${src}${r_first}:${src}${r_last}"
            wc.cell(r, col, f"=INDEX({rng},MATCH($A{r},{rg},0))")
        wc.cell(r, 5).number_format = "dd/mm/yyyy"
        for c in range(1, 6):
            cell = wc.cell(r, c)
            cell.font = Font(name=FONT, bold=(c == 4))
            cell.border = bord
            if c != 2 and c != 3:
                cell.alignment = Alignment(horizontal="center")
    wc.conditional_formatting.add(f"D4:D{3 + n_c}",
                                  DataBarRule(start_type="num", start_value=0, end_type="max", color="F5871F"))
    for c, w in zip("ABCDE", (7, 40, 28, 13, 20)):
        wc.column_dimensions[c].width = w
    wc.freeze_panes = "A4"

    # ============ feuille Détail (une ligne par chant et par prière) ============
    wd = wb.create_sheet("Détail")
    for i, t in enumerate(["Date", "Section", "Chant (tel qu'écrit dans la prière)", "N° affiché", "Chant (normalisé)"], start=1):
        style_entete(wd.cell(1, i, t))
    r = 2
    for pr in prieres:
        for section, num, titre in pr["chants"]:
            vals = [pr["date"], section, titre, num, cat[canonique(titre)]["titre"]]
            for c, v in enumerate(vals, start=1):
                cell = wd.cell(r, c, v)
                cell.font = base
                if c == 1:
                    cell.number_format = "dd/mm/yyyy"
            r += 1
    for c, w in zip("ABCDE", (13, 26, 38, 11, 38)):
        wd.column_dimensions[c].width = w
    wd.freeze_panes = "A2"
    wd.auto_filter.ref = f"A1:E{r - 1}"

    wb.save(chemin)


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--sortie", default=str(ROOT / "analyse_chants.xlsx"))
    ap.add_argument("--carnets", default=str(ROOT / "carnet chants"), help="dossier des PDF de carnets")
    ap.add_argument("--prieres", default=str(ROOT / "site" / "prieres"), help="dossier des HTML de prières")
    ap.add_argument("--depuis", type=dt.date.fromisoformat, metavar="AAAA-MM-JJ",
                    help="exclut d'office (case Inclure = 0) les prières avant cette date")
    a = ap.parse_args()

    carnets_dir = Path(a.carnets)
    carnets = [
        (LABEL_PRINCIPAL, lire_carnet_principal(carnets_dir / CARNET_PRINCIPAL)),
        (LABEL_BONUS, lire_carnet_bonus(carnets_dir / CARNET_BONUS)),
    ]
    prieres = lire_prieres(Path(a.prieres))
    if not prieres:
        sys.exit(f"Aucune prière AAAA-MM-JJ.html dans {a.prieres}")
    cat = construire_catalogue(carnets, prieres)
    ecrire_excel(a.sortie, cat, prieres, a.depuis)

    for label, chants in carnets:
        print(f"{label} : {len(chants)} chants")
    print(f"Prières : {', '.join(p['date'].isoformat() for p in prieres)}")
    hors = [e["titre"] for e in cat.values() if not e["en_carnet"]]
    if hors:
        print("Chants utilisés mais absents des carnets (ou titre à aligner dans ALIASES) :", ", ".join(hors))
    print(f"Excel écrit : {a.sortie}")


if __name__ == "__main__":
    main()
