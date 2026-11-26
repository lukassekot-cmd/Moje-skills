import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nabytok import engine  # noqa: E402
from nabytok.export_xlsx import export_xlsx  # noqa: E402
from nabytok.nesting import nest_material  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_example():
    with open(os.path.join(HERE, "priklady", "liptovska.nkp"), encoding="utf-8") as f:
        return json.load(f)


def by_mat(res):
    return {s["mat"]: s for s in res["summary"]}


def test_example_matches_original_calculation():
    res = engine.compute(load_example())
    s = by_mat(res)
    assert round(s["U16"]["m2"], 2) == 67.57
    assert s["U16"]["dosky"] == 14
    assert round(s["WAL"]["m2"], 2) == 23.07
    assert s["WAL"]["dosky"] == 5
    assert s["FLEX"]["dosky"] == "podľa dodávateľa"
    edges = {(e["dekor"], e["hrubka"]): e["bm"] for e in res["edges"]}
    assert round(edges[("U16007 light beige", 2)], 2) == 135.66
    assert round(edges[("H251 walnut", 2)], 2) == 45.66
    assert not [w for w in res["warnings"] if "nezmestí" in w]


def test_nesting_respects_grain_and_counts_boards():
    r = nest_material([(2565, 600, 3, "bok")], 2800, 2070, True, 4, 10)
    assert r["dosky"] == 1
    r = nest_material([(2565, 600, 4, "bok")], 2800, 2070, True, 4, 10)
    assert r["dosky"] == 2
    bad = nest_material([(3275, 450, 1, "doska")], 2800, 2070, False, 4, 10)
    assert bad["nezmestia"]


def kitchen_base(**kw):
    p = engine.new_project()
    z = engine.new_zostava("korpus", "Spodná 600")
    z["params"].update(dict(sirka=600, vyska=780, hlbka=560, sokel=100, nozicky=True, vrch="spojky",
                            cela="Z 390; Z", mat_korpus="BI18", mat_cela="U16"))
    z["params"].update(kw)
    p["zostavy"].append(z)
    return p


def test_korpus_drawers():
    res = engine.compute(kitchen_base())
    names = {r["nazov"]: r for r in res["rows"]}
    assert names["Bok"]["L"] == 780 and names["Bok"]["W"] == 560 and names["Bok"]["ks"] == 2
    assert names["Dno"]["L"] == 564
    assert names["Spojka"]["ks"] == 2
    fronts = [r for r in res["rows"] if r["nazov"] == "Čelo zásuvky"]
    assert sorted(f["L"] for f in fronts) == [387, 387]
    assert all(f["W"] == 597 for f in fronts)
    hw = {h["polozka"]: h for h in res["hw"]}
    assert "Zásuvka LEGRABOX F" in hw and hw["Zásuvka LEGRABOX F"]["ks"] == "2"
    assert hw["Nožička rektifikovateľná"]["ks"] == "4"
    assert hw["Úchytka"]["ks"] == "2"
    dna = [r for r in res["rows"] if r["nazov"] == "Dno zásuvky"]
    assert all(d["L"] == 564 - 35 and d["W"] == 490 for d in dna)
    assert sum(d["ks"] for d in dna) == 2
    assert all(c["stav"] == "✓" for c in res["checks"])


def test_wardrobe_sections_hinges_and_rest_height():
    p = engine.new_project()
    z = engine.new_zostava("korpus", "Šatník")
    z["params"].update(dict(sirka=1545, vyska=2365, hlbka=580, sekcie=2, police_nast=2, tyce=1,
                            cela="D3", mat_korpus="U16", mat_cela="U16"))
    p["zostavy"].append(z)
    res = engine.compute(p)
    doors = [r for r in res["rows"] if r["nazov"] == "Dvierka"][0]
    assert doors["ks"] == 3 and doors["W"] == 512 and doors["L"] == 2362
    hw = {h["polozka"]: h for h in res["hw"]}
    assert hw["Pánt s tlmením"]["ks"] == "15"
    assert [r for r in res["rows"] if r["nazov"] == "Priečka"][0]["L"] == 2329
    assert hw["Nosič police"]["ks"] == "16"


def test_parse_cela_errors():
    rows, errs = engine.parse_cela("D2; X 5")
    assert errs
    rows, errs = engine.parse_cela("D2; Z")
    assert errs  # dva riadky bez výšky


def test_cut_size_subtracts_edges():
    res = engine.compute(kitchen_base())
    f = [r for r in res["rows"] if r["nazov"] == "Čelo zásuvky"][0]
    assert f["rL"] == f["L"] - 4 and f["rW"] == f["W"] - 4


def test_export_xlsx(tmp_path):
    proj = load_example()
    res = engine.compute(proj)
    out = tmp_path / "x.xlsx"
    export_xlsx(proj, res, str(out))
    from openpyxl import load_workbook
    wb = load_workbook(out)
    assert {"A Kusovník", "B Materiál", "C Hrany", "D Kovanie", "Nárezový plán"} <= set(wb.sheetnames)
    assert wb["A Kusovník"].max_row == res["totals"]["dielcov"] + 1
