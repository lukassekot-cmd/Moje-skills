"""Výpočtové jadro: generovanie dielcov, súhrn materiálu, hrany, kovanie, kontrola."""
import copy
import math
import re
from collections import OrderedDict, defaultdict

from .nesting import nest_material

VERSION = "1.0"

DEFAULT_SETTINGS = {
    "skara": 3.0,            # medzera čiel naložených (spolu na spoj)
    "skara_vlozene": 2.0,    # medzera vložených čiel po obvode
    "prid_hrany": 10.0,      # % prídavok na hrany
    "rez": 4.0,              # hrúbka pílového kotúča (mm)
    "orez": 10.0,            # orez okraja dosky (mm)
    "odsadenie_polic": 20.0, # nastaviteľné police odsadené od čela/chrbta
}

DEFAULT_MATERIALS = [
    {"kod": "U16", "nazov": "DTD Pfleiderer U16007 SD light beige", "hrubka": 18, "textura": False,
     "hrana": "U16007 light beige", "dl": 2800, "sir": 2070, "odpad": 12},
    {"kod": "WAL", "nazov": "DTD Unilin 0H251 W06 walnut medium brown", "hrubka": 18, "textura": True,
     "hrana": "H251 walnut", "dl": 2800, "sir": 2070, "odpad": 15},
    {"kod": "BI18", "nazov": "DTD biela 18 mm", "hrubka": 18, "textura": False,
     "hrana": "biela", "dl": 2800, "sir": 2070, "odpad": 10},
    {"kod": "BI16", "nazov": "DTD biela 16 mm – dná zásuviek", "hrubka": 16, "textura": False,
     "hrana": "", "dl": 2800, "sir": 2070, "odpad": 10},
    {"kod": "HDF", "nazov": "HDF biela 3 mm – chrbty", "hrubka": 3, "textura": False,
     "hrana": "", "dl": 2800, "sir": 2070, "odpad": 10},
    {"kod": "MDF19", "nazov": "MDF 19 mm surová", "hrubka": 19, "textura": False,
     "hrana": "", "dl": 2800, "sir": 2070, "odpad": 10},
]

EDGE_VALUES = (0, 0.4, 0.5, 0.8, 1, 2)
NL_STANDARD = (270, 300, 350, 400, 450, 500, 550, 600, 650)

KORPUS_DEFAULTS = {
    "sirka": 600, "vyska": 720, "hlbka": 560,
    "sokel": 0, "sokel_diel": True,
    "vrch": "strop",            # strop | spojky | ziadny
    "dno": True,
    "sekcie": 1,
    "nadstavec": 0,             # vzdialenosť od vrchu korpusu po vrch medzidosky, 0 = bez
    "police_nast": 0,           # na sekciu
    "police_pevne": 0,          # na sekciu
    "tyce": 0,                  # počet tyčí (sekcií s tyčou)
    "chrbat": "HDF",            # HDF | DTD | ziadny
    "cela": "D1",
    "cela_typ": "nalozene",     # nalozene | vlozene
    "otvaranie": "uchytka",     # uchytka | push | podhmat | bez
    "presah_podhmat": 0,
    "otvoreny": False,          # viditeľné hrany korpusu 2 mm
    "zavesna": False,
    "nozicky": False,
    "mat_korpus": "BI18",
    "mat_cela": "U16",
    "mat_chrbat": "HDF",
    "mat_dno_zasuviek": "BI16",
    "hrana_korpus_viditelna": 2,
    "hrana_korpus_skryta": 0.5,
    "hrana_cela": 2,
}

TYPY = OrderedDict([("korpus", "Parametrický korpus"), ("vlastne", "Vlastné dielce")])


def new_project(nazov="Nová zákazka"):
    return {
        "verzia": VERSION,
        "nazov": nazov,
        "nastavenia": dict(DEFAULT_SETTINGS),
        "materialy": copy.deepcopy(DEFAULT_MATERIALS),
        "zostavy": [],
    }


def new_zostava(typ="korpus", nazov=None):
    z = {"nazov": nazov or ("Korpus" if typ == "korpus" else "Vlastné dielce"), "typ": typ,
         "zdroj": "", "poznamka": "", "params": {}, "dielce": [], "kovanie": []}
    if typ == "korpus":
        z["params"] = dict(KORPUS_DEFAULTS)
    return z


def _num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", "."))
    except ValueError:
        return default


def fmt(v):
    """Pekné číslo – bez zbytočných desatinných miest."""
    v = round(float(v), 1)
    return str(int(v)) if v == int(v) else str(v).replace(".", ",")


def part(nazov, mat, L, W, ks, hrany=(0, 0, 0, 0), pozn="", hrana_dlzka=0, konf=0, clamex=0):
    return {"nazov": nazov, "mat": mat, "L": round(L, 1), "W": round(W, 1), "ks": int(ks),
            "D1": hrany[0], "D2": hrany[1], "S1": hrany[2], "S2": hrany[3],
            "hrana_dlzka": hrana_dlzka, "pozn": pozn, "konf": konf, "clamex": clamex}


# ---------------------------------------------------------------- čelá
FRONT_RE = re.compile(r"^\s*([DZOB])(\d*)(?:\s*@\s*|\s+)?(\d+(?:[.,]\d+)?)?\s*$", re.I)


def parse_cela(text):
    """'Z 250; Z 250; D2' – riadky zdola nahor. D=dvierka, Z=zásuvka, O=otvorené, B=pevná blenda.
    Číslo za písmenom = počet vedľa seba, číslo za medzerou/@ = výška zóny (bez = zvyšok)."""
    rows, errors = [], []
    if not text or not str(text).strip():
        return rows, errors
    for tok in re.split(r"[;\n]+", str(text)):
        if not tok.strip():
            continue
        m = FRONT_RE.match(tok)
        if not m:
            errors.append(f"Nerozumiem zápisu čiel: '{tok.strip()}'")
            continue
        typ = m.group(1).upper()
        n = int(m.group(2)) if m.group(2) else 1
        h = _num(m.group(3), 0) if m.group(3) else 0
        rows.append({"typ": typ, "n": max(1, n), "h": h})
    rest = [r for r in rows if r["h"] == 0]
    if len(rest) > 1:
        errors.append("Výšku bez čísla (zvyšok) môže mať iba jeden riadok čiel.")
    return rows, errors


def legrabox_height(front_h):
    if front_h < 120:
        return "N"
    if front_h < 160:
        return "M"
    if front_h < 200:
        return "K"
    if front_h < 260:
        return "C"
    return "F"


def nl_for_depth(depth):
    ok = [n for n in NL_STANDARD if n <= depth - 10]
    return ok[-1] if ok else NL_STANDARD[0]


def hinges_for(h):
    if h <= 900:
        return 2
    if h <= 1600:
        return 3
    if h <= 2000:
        return 4
    return 5


# ---------------------------------------------------------------- korpus
def build_korpus(z, mats, st):
    p = dict(KORPUS_DEFAULTS)
    p.update(z.get("params", {}))
    W, H, D = _num(p["sirka"]), _num(p["vyska"]), _num(p["hlbka"])
    mk, mc = p["mat_korpus"], p["mat_cela"]
    t = _num(mats.get(mk, {}).get("hrubka", 18), 18)
    tc = _num(mats.get(mc, {}).get("hrubka", 18), 18)
    n = max(1, int(_num(p["sekcie"], 1)))
    nad = _num(p["nadstavec"])
    he_vis = _num(p["hrana_korpus_viditelna"], 2)
    he_hid = _num(p["hrana_korpus_skryta"], 0.5)
    he_c = _num(p["hrana_cela"], 2)
    front_edge = he_vis if p["otvoreny"] else he_hid
    parts, hw, warn, checks = [], [], [], []

    def addhw(polozka, typ, ks, pozn=""):
        if ks:
            hw.append({"polozka": polozka, "typ": typ, "ks": ks, "pozn": pozn})

    if W <= 0 or H <= 0 or D <= 0:
        warn.append("Šírka, výška a hĺbka musia byť väčšie ako 0.")
        return parts, hw, warn, checks

    iw = W - 2 * t
    sw = (iw - (n - 1) * t) / n
    chrbat = p["chrbat"]
    d_in = D - (t if chrbat == "DTD" else 0)

    parts.append(part("Bok", mk, H, D, 2, (front_edge, 0, 0, 0)))
    top_t = 0
    if p["vrch"] == "strop":
        parts.append(part("Strop", mk, iw, D, 1, (front_edge, 0, 0, 0), konf=6))
        top_t = t
    elif p["vrch"] == "spojky":
        parts.append(part("Spojka", mk, iw, 100, 2, konf=4))
        top_t = t
    bot_t = 0
    if p["dno"]:
        parts.append(part("Dno", mk, iw, D, 1, (front_edge, 0, 0, 0), konf=6))
        bot_t = t
    if nad > 0:
        if nad >= H - bot_t - t:
            warn.append("Nadstavec je vyšší ako korpus.")
        parts.append(part("Medzidoska nadstavca", mk, iw, D, 1, (front_edge, 0, 0, 0), konf=6))
    if n > 1:
        if nad > 0:
            parts.append(part("Priečka dolná", mk, H - nad - t - bot_t, d_in, n - 1, (front_edge, 0, 0, 0), konf=4))
            parts.append(part("Priečka nadstavca", mk, nad - top_t, d_in, n - 1, (front_edge, 0, 0, 0), konf=4))
        else:
            parts.append(part("Priečka", mk, H - top_t - bot_t, d_in, n - 1, (front_edge, 0, 0, 0), konf=4))

    pn = int(_num(p["police_nast"])) * n
    pp = int(_num(p["police_pevne"])) * n
    off = _num(st.get("odsadenie_polic", 20))
    if pn:
        parts.append(part("Polica nastaviteľná", mk, sw - 1, d_in - off, pn, (front_edge, 0, 0, 0)))
        addhw("Nosič police", "kolíkový 5 mm", 4 * pn)
    if pp:
        if p["otvoreny"]:
            parts.append(part("Polica pevná", mk, sw, d_in, pp, (front_edge, 0, 0, 0), clamex=4,
                              pozn="bez viditeľných spojov"))
        else:
            parts.append(part("Polica pevná", mk, sw, d_in, pp, (front_edge, 0, 0, 0), konf=6))

    if chrbat == "HDF":
        parts.append(part("Chrbát", p["mat_chrbat"] or "HDF", H, W, 1))
    elif chrbat == "DTD":
        parts.append(part("Chrbát vložený", mk, H - top_t - bot_t, iw, 1, konf=8))

    tyce = int(_num(p["tyce"]))
    if tyce:
        addhw("Šatníková tyč", f"dĺžka {fmt(sw - 4)} mm", tyce)
        addhw("Držiak tyče", "", 2 * tyce)

    S = _num(p["sokel"])
    if S > 0 and p["sokel_diel"]:
        parts.append(part("Sokel", mc, W, S - 2, 1, (0.5, 0, 0, 0)))
    if S > 0 and p["nozicky"]:
        addhw("Nožička rektifikovateľná", f"{fmt(S)} mm", 4 if W <= 900 else 6)
    elif S == 0 and not p["zavesna"]:
        addhw("Rektifikačné kovanie dna", "", 4)
    if p["zavesna"]:
        addhw("Záves hornej skrinky", "napr. Camar 807", 2)

    # ---- čelá
    rows, errs = parse_cela(p["cela"])
    warn += errs
    vloz = p["cela_typ"] == "vlozene"
    sk = _num(st["skara"], 3)
    skv = _num(st["skara_vlozene"], 2)
    zone_total = (H - top_t - bot_t) if vloz else H
    fixed = sum(r["h"] for r in rows if r["h"] > 0)
    rest_rows = [r for r in rows if r["h"] == 0]
    if rest_rows:
        rest_rows[0]["h"] = zone_total - fixed - (t * (len(rows) - 1) if vloz else 0)
        if rest_rows[0]["h"] <= 0:
            warn.append("Súčet výšok čiel je väčší ako korpus.")
    elif rows and abs(fixed - zone_total) > 0.5 and not vloz:
        checks.append({"popis": "Súčet zón čiel = výška korpusu", "vypocet": fmt(fixed),
                       "vykres": fmt(zone_total), "stav": "⚠"})
    presah = _num(p["presah_podhmat"]) if p["otvaranie"] == "podhmat" else 0
    nl = nl_for_depth(D - (5 if not vloz else tc + 5))
    uchytky = 0
    hinge_kind = "Blum CLIP top BLUMOTION 110° " + ("vložený" if vloz else "naložený")
    for i, r in enumerate(rows):
        cnt = r["n"]
        if vloz:
            fw = (iw - (cnt + 1) * skv) / cnt
            fh = r["h"] - 2 * skv
        else:
            fw = W / cnt - sk
            fh = r["h"] - sk
        fh_out = fh + (presah if i == 0 else 0)
        if r["typ"] == "O":
            continue
        if fw <= 0 or fh <= 0:
            warn.append(f"Čelo riadku {i + 1} má nulový alebo záporný rozmer.")
            continue
        nazov = {"D": "Dvierka", "Z": "Čelo zásuvky", "B": "Blenda pevná"}[r["typ"]]
        parts.append(part(nazov + (" vložené" if vloz else ""), mc, fh_out, fw, cnt, (he_c,) * 4,
                          pozn="podhmat" if presah and i == 0 else ""))
        if r["typ"] == "D":
            hk = hinges_for(fh_out)
            if p["otvaranie"] == "push":
                addhw("Pánt bez tlmenia (push)", "Blum CLIP top 110°", hk * cnt)
                addhw("Otvárací systém push", "Blum TIP-ON", cnt)
            else:
                addhw("Pánt s tlmením", hinge_kind, hk * cnt)
            if p["otvaranie"] == "uchytka":
                uchytky += cnt
        elif r["typ"] == "Z":
            if cnt == n:
                lw = sw                      # jedna zásuvka v každej sekcii
            elif n == 1:
                lw = (iw - (cnt - 1) * t) / cnt
            else:
                lw = (iw - (cnt - 1) * t) / cnt
                warn.append(f"Riadok čiel {i + 1}: počet zásuviek ({cnt}) nesedí s počtom sekcií ({n}).")
            if cnt > 1 and n == 1:
                parts.append(part("Priečka zásuviek", mk, r["h"], d_in, cnt - 1, (front_edge, 0, 0, 0), konf=4))
            vyska = legrabox_height(fh)
            addhw(f"Zásuvka LEGRABOX {vyska}", f"Blum LEGRABOX pure {vyska}, NL {nl}", cnt,
                  f"LW {fmt(lw)}")
            parts.append(part("Dno zásuvky", p["mat_dno_zasuviek"] or "BI16", lw - 35, nl - 10, cnt,
                              pozn=f"LEGRABOX LW {fmt(lw)} − 35 × NL {nl} − 10"))
            if p["otvaranie"] == "push":
                addhw("Otvárací systém push zásuvky", "Blum TIP-ON BLUMOTION", cnt)
            if p["otvaranie"] == "uchytka":
                uchytky += cnt
    if uchytky:
        addhw("Úchytka", "podľa výkresu", uchytky)

    # ---- kontrola
    checks.append({"popis": "Šírka: 2 boky + priečky + sekcie",
                   "vypocet": f"2×{fmt(t)} + {n - 1}×{fmt(t)} + {n}×{fmt(sw)} = {fmt(2 * t + (n - 1) * t + n * sw)}",
                   "vykres": fmt(W), "stav": "✓" if abs(2 * t + (n - 1) * t + n * sw - W) < 0.6 else "⚠"})
    if sw < 100:
        warn.append(f"Svetlá šírka sekcie je len {fmt(sw)} mm.")
    return parts, hw, warn, checks


# ---------------------------------------------------------------- projekt
def material_map(project):
    return {m["kod"]: m for m in project.get("materialy", [])}


def compute(project):
    """Vráti dict s kusovníkom, súhrnom materiálu, hranami, kovaním, kontrolou a varovaniami."""
    st = dict(DEFAULT_SETTINGS)
    st.update(project.get("nastavenia", {}))
    mats = material_map(project)
    rows, hw_all, warns, checks = [], [], [], []
    c = 0
    for zi, z in enumerate(project.get("zostavy", [])):
        zn = z.get("nazov") or f"Zostava {zi + 1}"
        parts, hw, w, ch = [], [], [], []
        if z.get("typ") == "korpus":
            parts, hw, w, ch = build_korpus(z, mats, st)
        parts = parts + [dict(x) for x in z.get("dielce", [])]
        hw = hw + [dict(x) for x in z.get("kovanie", [])]
        for x in w:
            warns.append(f"{zn}: {x}")
        for x in ch:
            checks.append(dict(x, zostava=zn))
        for x in parts:
            c += 1
            m = mats.get(x.get("mat"))
            if m is None:
                warns.append(f"{zn} / {x.get('nazov')}: neznámy materiál '{x.get('mat')}'")
                m = {"kod": x.get("mat"), "nazov": x.get("mat"), "hrubka": 0, "textura": False,
                     "hrana": "", "dl": 0, "sir": 0, "odpad": 0}
            L, Wd, ks = _num(x.get("L")), _num(x.get("W")), int(_num(x.get("ks"), 1))
            e = [_num(x.get(k)) for k in ("D1", "D2", "S1", "S2")]
            rl, rw = L - e[2] - e[3], Wd - e[0] - e[1]
            rows.append({
                "c": c, "zostava": zn, "nazov": x.get("nazov", ""), "mat": m["kod"], "mat_nazov": m["nazov"],
                "hrubka": m["hrubka"], "L": L, "W": Wd, "ks": ks, "rL": rl, "rW": rw,
                "textura": "áno – pozdĺž dĺžky" if m.get("textura") else "nie",
                "D1": e[0], "D2": e[1], "S1": e[2], "S2": e[3],
                "m2": L * Wd * ks / 1e6, "hrana_dlzka": _num(x.get("hrana_dlzka")),
                "zdroj": z.get("zdroj", ""), "pozn": x.get("pozn", ""),
                "konf": _num(x.get("konf")) * ks, "clamex": _num(x.get("clamex")) * ks,
            })
        for h in hw:
            hw_all.append({"zostava": zn, "polozka": h.get("polozka", ""), "typ": h.get("typ", ""),
                           "ks": h.get("ks", ""), "pozn": h.get("pozn", "")})

    # materiál + nárez
    area = defaultdict(float)
    for r in rows:
        area[r["mat"]] += r["m2"]
    summary = []
    for kod, a in area.items():
        m = mats.get(kod, {"nazov": kod, "hrubka": 0, "odpad": 0, "dl": 0, "sir": 0, "textura": False})
        odp = _num(m.get("odpad"))
        aw = a * (1 + odp / 100)
        dl, sir = _num(m.get("dl")), _num(m.get("sir"))
        if dl > 0 and sir > 0:
            fa = dl * sir / 1e6
            n_area = math.ceil(aw / fa - 1e-9) if aw > 0 else 0
            pieces = [(r["L"], r["W"], r["ks"], f'{r["zostava"]} / {r["nazov"]}') for r in rows if r["mat"] == kod]
            nres = nest_material(pieces, dl, sir, bool(m.get("textura")), _num(st["rez"]), _num(st["orez"]))
            for bad in nres["nezmestia"]:
                warns.append(f"Dielec sa nezmestí na formát {fmt(dl)}×{fmt(sir)} ({m['nazov']}): {bad}")
            summary.append({"mat": kod, "nazov": m["nazov"], "hrubka": m.get("hrubka"), "m2": a, "odpad": odp,
                            "m2_odpad": aw, "format": f"{fmt(dl)}×{fmt(sir)}", "dosky": n_area,
                            "dosky_narez": nres["dosky"], "vyuzitie": nres["vyuzitie"], "plan": nres["plan"]})
        else:
            summary.append({"mat": kod, "nazov": m["nazov"], "hrubka": m.get("hrubka"), "m2": a, "odpad": odp,
                            "m2_odpad": aw, "format": "–", "dosky": "podľa dodávateľa",
                            "dosky_narez": "–", "vyuzitie": "–", "plan": []})

    # hrany
    edges = defaultdict(float)
    for r in rows:
        m = mats.get(r["mat"], {})
        dekor = m.get("hrana") or ""
        if not dekor:
            continue
        if r["hrana_dlzka"]:
            hr = max(r["D1"], r["D2"], r["S1"], r["S2"]) or 2
            edges[(dekor, hr)] += r["hrana_dlzka"] * r["ks"] / 1000
            continue
        for k, ln in (("D1", r["L"]), ("D2", r["L"]), ("S1", r["W"]), ("S2", r["W"])):
            if r[k]:
                edges[(dekor, r[k])] += ln * r["ks"] / 1000
    pr = _num(st["prid_hrany"])
    edge_rows = [{"dekor": d, "hrubka": h, "bm": v, "bm_prid": v * (1 + pr / 100)}
                 for (d, h), v in sorted(edges.items(), key=lambda kv: (kv[0][0], -kv[0][1]))]

    # kovanie – súhrn
    agg = OrderedDict()
    for h in hw_all:
        key = (h["polozka"], h["typ"])
        try:
            ks = float(str(h["ks"]).replace(",", "."))
        except ValueError:
            ks = None
        a = agg.setdefault(key, {"polozka": h["polozka"], "typ": h["typ"], "ks": 0, "ks_text": [], "zostavy": []})
        if ks is None:
            a["ks_text"].append(str(h["ks"]))
        else:
            a["ks"] += ks
        a["zostavy"].append(f'{h["zostava"]}' + (f' ({h["pozn"]})' if h["pozn"] else ""))
    konf = sum(r["konf"] for r in rows)
    clam = sum(r["clamex"] for r in rows)
    if konf:
        agg[("Konfirmát 7×50 + krytka", "")] = {"polozka": "Konfirmát 7×50 + krytka", "typ": "odhad zo spojov",
                                                "ks": konf, "ks_text": [], "zostavy": ["automaticky"]}
    if clam:
        agg[("Skrytý spoj políc", "")] = {"polozka": "Skrytý spoj pevných viditeľných políc",
                                          "typ": "Lamello Clamex P-14", "ks": clam, "ks_text": [],
                                          "zostavy": ["automaticky"]}
    hw_sum = []
    for a in agg.values():
        ks = fmt(a["ks"]) if a["ks"] else ""
        if a["ks_text"]:
            ks = " + ".join([x for x in [ks] + a["ks_text"] if x])
        hw_sum.append({"polozka": a["polozka"], "typ": a["typ"], "ks": ks, "pozn": "; ".join(a["zostavy"])})

    return {"rows": rows, "summary": summary, "edges": edge_rows, "hw": hw_sum, "hw_detail": hw_all,
            "checks": checks, "warnings": warns,
            "totals": {"dielcov": len(rows), "ks": sum(r["ks"] for r in rows)}}
