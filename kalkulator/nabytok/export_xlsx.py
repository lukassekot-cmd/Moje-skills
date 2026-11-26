"""Export výsledkov do Excelu (.xlsx)."""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .engine import fmt

HEAD_FILL = PatternFill("solid", fgColor="5B5B3A")


def edge_txt(v):
    if not v:
        return "–"
    return fmt(v)


def _sheet(ws, header, rows, widths=None):
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for r in rows:
        ws.append(list(r))
    ws.freeze_panes = "A2"
    for i in range(1, len(header) + 1):
        col = get_column_letter(i)
        mx = max((len(str(c.value)) for c in ws[col] if c.value is not None), default=8)
        ws.column_dimensions[col].width = min(max(7, mx + 2), 60)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")


def export_xlsx(project, res, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "A Kusovník"
    _sheet(ws, ["Č.", "Zostava", "Názov dielca", "Materiál/dekor", "Hrúbka", "Dĺžka", "Šírka", "Ks",
                "Dĺžka rezná", "Šírka rezná", "Textúra", "D1", "D2", "Š1", "Š2", "m²", "Zdroj", "Poznámka"],
           [[r["c"], r["zostava"], r["nazov"], r["mat_nazov"], r["hrubka"], r["L"], r["W"], r["ks"],
             round(r["rL"], 1), round(r["rW"], 1), r["textura"], edge_txt(r["D1"]), edge_txt(r["D2"]),
             edge_txt(r["S1"]), edge_txt(r["S2"]), round(r["m2"], 2), r["zdroj"], r["pozn"]]
            for r in res["rows"]])
    _sheet(wb.create_sheet("B Materiál"),
           ["Materiál", "Hrúbka", "m² čisté", "Odpad %", "m² s odpadom", "Formát", "Dosky (plocha)",
            "Dosky (nárezový plán)", "Využitie nárezu %"],
           [[s["nazov"], s["hrubka"], round(s["m2"], 2), s["odpad"], round(s["m2_odpad"], 2), s["format"],
             s["dosky"], s["dosky_narez"], s["vyuzitie"]] for s in res["summary"]])
    _sheet(wb.create_sheet("C Hrany"), ["Dekor", "Hrúbka (mm)", "bm čisté", "bm s prídavkom"],
           [[e["dekor"], fmt(e["hrubka"]), round(e["bm"], 2), round(e["bm_prid"], 2)] for e in res["edges"]])
    _sheet(wb.create_sheet("D Kovanie"), ["Položka", "Typ/výrobca", "Ks", "Poznámka / zostavy"],
           [[h["polozka"], h["typ"], h["ks"], h["pozn"]] for h in res["hw"]])
    _sheet(wb.create_sheet("Kontrola"), ["Zostava", "Kontrola", "Výpočet", "Výkres", "Stav"],
           [[c.get("zostava", ""), c.get("popis", ""), c.get("vypocet", ""), c.get("vykres", ""), c.get("stav", "")]
            for c in res["checks"]])
    _sheet(wb.create_sheet("Varovania"), ["Varovanie"], [[w] for w in res["warnings"]] or [["Bez varovaní"]])
    plan_rows = []
    for s in res["summary"]:
        for bi, board in enumerate(s["plan"], 1):
            for (x, y, w, h, popis, rot) in board:
                plan_rows.append([s["nazov"], bi, round(x), round(y), round(w, 1), round(h, 1),
                                  "áno" if rot else "nie", popis])
    _sheet(wb.create_sheet("Nárezový plán"),
           ["Materiál", "Doska č.", "X", "Y", "Dĺžka", "Šírka", "Otočené", "Dielec"], plan_rows)
    info = wb.create_sheet("Zákazka", 0)
    info.append(["Zákazka", project.get("nazov", "")])
    info.append(["Dielcov (riadkov)", res["totals"]["dielcov"]])
    info.append(["Kusov spolu", res["totals"]["ks"]])
    info.append(["Varovaní", len(res["warnings"])])
    info.column_dimensions["A"].width = 22
    info.column_dimensions["B"].width = 60
    wb.save(path)
