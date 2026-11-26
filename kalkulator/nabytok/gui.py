"""Okenné rozhranie (Tkinter) – Kalkulátor spotreby materiálu pre korpusový nábytok."""
import copy
import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import engine
from .engine import fmt
from .export_xlsx import export_xlsx

APP_NAME = "Kalkulátor spotreby materiálu – nábytok"
FILE_TYPES = [("Projekt kalkulátora", "*.nkp"), ("JSON", "*.json"), ("Všetky súbory", "*.*")]
EDGE_CHOICES = ["0", "0.5", "1", "2"]

HELP_CELA = (
    "Čelá – riadky zdola nahor, oddelené bodkočiarkou:\n"
    "  D2       = 2 dvierka vedľa seba, výška = zvyšok\n"
    "  D3 470   = 3 dvierka, zóna 470 mm\n"
    "  Z 250    = zásuvka, zóna 250 mm\n"
    "  Z2 200   = 2 zásuvky vedľa seba\n"
    "  O 300    = otvorená zóna (bez čela)\n"
    "  B 100    = pevná blenda\n"
    "Príklad kuchynskej zásuvkovej: Z 387; Z\n"
    "Príklad šatníka s nadstavcom: D3; D3 470"
)


def resource_path(*rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *rel)


# --------------------------------------------------------------------- tabuľkový editor
class TableEditor(ttk.Frame):
    """Editor zoznamu záznamov (dict) – Treeview + formulár."""

    def __init__(self, master, columns, rows, choices=None):
        super().__init__(master)
        self.columns = columns  # [(key, label, width, kind)] kind: str|num|bool|edge|mat
        self.rows = [dict(r) for r in rows]
        self.choices = choices or {}
        tf = ttk.Frame(self)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=[c[0] for c in columns], show="headings", height=10,
                                 selectmode="browse")
        for key, label, width, _ in columns:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w", stretch=key in ("nazov", "polozka", "pozn"))
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.LabelFrame(self, text="Záznam")
        form.pack(fill="x", pady=4)
        self.vars = {}
        per_row = 6
        for i, (key, label, width, kind) in enumerate(columns):
            r, c = divmod(i, per_row)
            ttk.Label(form, text=label).grid(row=r * 2, column=c, sticky="w", padx=3)
            if kind == "bool":
                v = tk.BooleanVar()
                w = ttk.Checkbutton(form, variable=v)
            elif kind in ("edge", "mat"):
                v = tk.StringVar()
                vals = EDGE_CHOICES if kind == "edge" else self.choices.get("mat", [])
                w = ttk.Combobox(form, textvariable=v, values=vals, width=max(6, min(14, width // 8)))
            else:
                v = tk.StringVar()
                w = ttk.Entry(form, textvariable=v, width=max(6, min(40, width // 7)))
            w.grid(row=r * 2 + 1, column=c, sticky="we", padx=3, pady=(0, 4))
            self.vars[key] = v
        for c in range(per_row):
            form.columnconfigure(c, weight=1)
        bf = ttk.Frame(self)
        bf.pack(fill="x")
        ttk.Button(bf, text="Pridať nový", command=self.add).pack(side="left", padx=2)
        ttk.Button(bf, text="Uložiť zmeny riadku", command=self.update).pack(side="left", padx=2)
        ttk.Button(bf, text="Duplikovať", command=self.duplicate).pack(side="left", padx=2)
        ttk.Button(bf, text="Zmazať", command=self.delete).pack(side="left", padx=2)
        self.refresh()

    def _val(self, kind, v):
        if kind == "bool":
            return bool(v.get())
        s = v.get().strip()
        if kind in ("num", "edge"):
            try:
                f = float(s.replace(",", ".")) if s else 0.0
                return int(f) if f == int(f) else f
            except ValueError:
                raise ValueError(f"'{s}' nie je číslo")
        return s

    def _read_form(self):
        rec = {}
        for key, label, _, kind in self.columns:
            try:
                rec[key] = self._val(kind, self.vars[key])
            except ValueError as e:
                messagebox.showerror("Chyba", f"{label}: {e}", parent=self)
                return None
        return rec

    def refresh(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            vals = []
            for key, _, _, kind in self.columns:
                v = r.get(key, "")
                if kind == "bool":
                    v = "áno" if v else "nie"
                vals.append(v)
            self.tree.insert("", "end", iid=str(i), values=vals)
        if select is not None and 0 <= select < len(self.rows):
            self.tree.selection_set(str(select))
            self.tree.see(str(select))

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _on_select(self, _=None):
        i = self._sel()
        if i is None:
            return
        r = self.rows[i]
        for key, _, _, kind in self.columns:
            v = r.get(key, "")
            if kind == "bool":
                self.vars[key].set(bool(v))
            else:
                self.vars[key].set("" if v is None else str(v))

    def add(self):
        rec = self._read_form()
        if rec is not None:
            self.rows.append(rec)
            self.refresh(len(self.rows) - 1)

    def update(self):
        i = self._sel()
        if i is None:
            messagebox.showinfo("Info", "Najprv vyberte riadok.", parent=self)
            return
        rec = self._read_form()
        if rec is not None:
            self.rows[i].update(rec)
            self.refresh(i)

    def duplicate(self):
        i = self._sel()
        if i is not None:
            self.rows.insert(i + 1, dict(self.rows[i]))
            self.refresh(i + 1)

    def delete(self):
        i = self._sel()
        if i is not None:
            del self.rows[i]
            self.refresh(min(i, len(self.rows) - 1))


PART_COLS = [("nazov", "Názov dielca", 200, "str"), ("mat", "Materiál", 70, "mat"), ("L", "Dĺžka", 60, "num"),
             ("W", "Šírka", 60, "num"), ("ks", "Ks", 40, "num"), ("D1", "D1", 40, "edge"),
             ("D2", "D2", 40, "edge"), ("S1", "Š1", 40, "edge"), ("S2", "Š2", 40, "edge"),
             ("hrana_dlzka", "Hrana dĺžka (tvar)", 90, "num"), ("konf", "Konfirmáty/ks", 70, "num"),
             ("clamex", "Clamex/ks", 60, "num"), ("pozn", "Poznámka", 200, "str")]
HW_COLS = [("polozka", "Položka", 220, "str"), ("typ", "Typ/výrobca", 220, "str"), ("ks", "Ks", 60, "str"),
           ("pozn", "Poznámka", 250, "str")]
MAT_COLS = [("kod", "Kód", 60, "str"), ("nazov", "Názov / dekor", 300, "str"), ("hrubka", "Hrúbka", 60, "num"),
            ("textura", "Textúra", 60, "bool"), ("hrana", "Dekor hrany", 150, "str"), ("dl", "Formát dĺžka", 80, "num"),
            ("sir", "Formát šírka", 80, "num"), ("odpad", "Odpad %", 60, "num")]


class ModalDialog(tk.Toplevel):
    def __init__(self, master, title, size="1000x650"):
        super().__init__(master)
        self.title(title)
        self.geometry(size)
        self.transient(master)
        self.result = None
        self.body = ttk.Frame(self, padding=8)
        self.body.pack(fill="both", expand=True)
        bf = ttk.Frame(self, padding=(8, 0, 8, 8))
        bf.pack(fill="x")
        ttk.Button(bf, text="Zrušiť", command=self.destroy).pack(side="right", padx=3)
        ttk.Button(bf, text="OK", command=self._ok).pack(side="right", padx=3)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _ok(self):
        r = self.collect()
        if r is not None:
            self.result = r
            self.destroy()

    def collect(self):
        return True

    def run(self):
        self.grab_set()
        self.wait_window()
        return self.result


class ListDialog(ModalDialog):
    def __init__(self, master, title, cols, rows, choices=None, hint=""):
        super().__init__(master, title)
        if hint:
            ttk.Label(self.body, text=hint, foreground="#555", wraplength=950).pack(anchor="w", pady=(0, 4))
        self.ed = TableEditor(self.body, cols, rows, choices)
        self.ed.pack(fill="both", expand=True)

    def collect(self):
        return self.ed.rows


class SettingsDialog(ModalDialog):
    LABELS = [("skara", "Škára naložených čiel (mm)"), ("skara_vlozene", "Škára vložených čiel po obvode (mm)"),
              ("prid_hrany", "Prídavok na hrany (%)"), ("rez", "Hrúbka rezu píly (mm)"),
              ("orez", "Orez okraja dosky (mm)"), ("odsadenie_polic", "Odsadenie nastaviteľných políc (mm)")]

    def __init__(self, master, settings):
        super().__init__(master, "Nastavenia výpočtu", "460x320")
        self.vars = {}
        for i, (k, lab) in enumerate(self.LABELS):
            ttk.Label(self.body, text=lab).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=str(settings.get(k, engine.DEFAULT_SETTINGS[k])))
            ttk.Entry(self.body, textvariable=v, width=10).grid(row=i, column=1, sticky="w", padx=6)
            self.vars[k] = v

    def collect(self):
        out = {}
        for k, lab in self.LABELS:
            try:
                out[k] = float(self.vars[k].get().replace(",", "."))
            except ValueError:
                messagebox.showerror("Chyba", f"{lab}: nie je číslo", parent=self)
                return None
        return out


class ZostavaDialog(ModalDialog):
    KORPUS_FIELDS = [
        ("Rozmery", [("sirka", "Šírka (mm)", "num"), ("vyska", "Výška korpusu (mm)", "num"),
                     ("hlbka", "Hĺbka korpusu bez čiel (mm)", "num"), ("sokel", "Sokel (mm, 0 = bez)", "num"),
                     ("sokel_diel", "Rátať dielec sokla", "bool"), ("nozicky", "Kuchynské nožičky", "bool"),
                     ("zavesna", "Závesná (horná) skrinka", "bool")]),
        ("Konštrukcia", [("vrch", "Vrch", ("strop", "spojky", "ziadny")), ("dno", "Dno", "bool"),
                         ("sekcie", "Počet sekcií (priečky)", "num"),
                         ("nadstavec", "Nadstavec – od vrchu po medzidosku (0 = bez)", "num"),
                         ("chrbat", "Chrbát", ("HDF", "DTD", "ziadny")), ("otvoreny", "Otvorený – viditeľné hrany", "bool")]),
        ("Vnútro", [("police_nast", "Nastaviteľné police / sekcia", "num"),
                    ("police_pevne", "Pevné police / sekcia", "num"), ("tyce", "Počet šatníkových tyčí", "num")]),
        ("Čelá", [("cela", "Čelá (zápis)", "str"), ("cela_typ", "Typ čiel", ("nalozene", "vlozene")),
                  ("otvaranie", "Otváranie", ("uchytka", "push", "podhmat", "bez")),
                  ("presah_podhmat", "Presah pre podhmat (mm)", "num")]),
        ("Materiály a hrany", [("mat_korpus", "Materiál korpusu", "mat"), ("mat_cela", "Materiál čiel", "mat"),
                               ("mat_chrbat", "Materiál chrbta (HDF)", "mat"),
                               ("mat_dno_zasuviek", "Dno zásuviek", "mat"),
                               ("hrana_korpus_viditelna", "Hrana korpusu viditeľná", "edge"),
                               ("hrana_korpus_skryta", "Hrana korpusu za čelom", "edge"),
                               ("hrana_cela", "Hrana čiel", "edge")]),
    ]

    def __init__(self, master, z, mat_codes):
        super().__init__(master, "Zostava – " + engine.TYPY.get(z["typ"], z["typ"]), "1050x720")
        self.z = copy.deepcopy(z)
        self.mat_codes = mat_codes
        top = ttk.Frame(self.body)
        top.pack(fill="x")
        self.v_nazov = tk.StringVar(value=self.z.get("nazov", ""))
        self.v_zdroj = tk.StringVar(value=self.z.get("zdroj", ""))
        self.v_pozn = tk.StringVar(value=self.z.get("poznamka", ""))
        for i, (lab, v, w) in enumerate((("Názov zostavy", self.v_nazov, 40), ("Zdroj (strany výkresu)", self.v_zdroj, 20),
                                         ("Poznámka", self.v_pozn, 40))):
            ttk.Label(top, text=lab).grid(row=0, column=i, sticky="w", padx=4)
            ttk.Entry(top, textvariable=v, width=w).grid(row=1, column=i, sticky="we", padx=4)
        nb = ttk.Notebook(self.body)
        nb.pack(fill="both", expand=True, pady=6)
        self.pvars = {}
        if self.z["typ"] == "korpus":
            f = ttk.Frame(nb, padding=6)
            nb.add(f, text="Parametre korpusu")
            self._korpus_form(f)
        fd = ttk.Frame(nb, padding=6)
        nb.add(fd, text="Vlastné dielce" if self.z["typ"] == "vlastne" else "Dielce navyše")
        self.ed_parts = TableEditor(fd, PART_COLS, self.z.get("dielce", []), {"mat": mat_codes})
        self.ed_parts.pack(fill="both", expand=True)
        fk = ttk.Frame(nb, padding=6)
        nb.add(fk, text="Kovanie navyše")
        self.ed_hw = TableEditor(fk, HW_COLS, self.z.get("kovanie", []))
        self.ed_hw.pack(fill="both", expand=True)

    def _korpus_form(self, f):
        p = dict(engine.KORPUS_DEFAULTS)
        p.update(self.z.get("params", {}))
        left = ttk.Frame(f)
        left.pack(side="left", fill="both", expand=True)
        col = 0
        for gi, (group, fields) in enumerate(self.KORPUS_FIELDS):
            lf = ttk.LabelFrame(left, text=group, padding=4)
            lf.grid(row=gi // 2 if gi < 4 else 2, column=gi % 2 if gi < 4 else 0, columnspan=1 if gi < 4 else 2,
                    sticky="nwe", padx=4, pady=4)
            for i, (key, lab, kind) in enumerate(fields):
                r, c = (i, 0) if gi < 4 else divmod(i, 4)
                cc = c * 2
                ttk.Label(lf, text=lab).grid(row=r, column=cc, sticky="w", padx=2, pady=1)
                if kind == "bool":
                    v = tk.BooleanVar(value=bool(p.get(key)))
                    w = ttk.Checkbutton(lf, variable=v)
                elif isinstance(kind, tuple):
                    v = tk.StringVar(value=str(p.get(key)))
                    w = ttk.Combobox(lf, textvariable=v, values=kind, state="readonly", width=12)
                elif kind == "mat":
                    v = tk.StringVar(value=str(p.get(key)))
                    w = ttk.Combobox(lf, textvariable=v, values=self.mat_codes, width=10)
                elif kind == "edge":
                    v = tk.StringVar(value=fmt(p.get(key) or 0).replace(",", "."))
                    w = ttk.Combobox(lf, textvariable=v, values=EDGE_CHOICES, width=6)
                else:
                    v = tk.StringVar(value=str(p.get(key)))
                    w = ttk.Entry(lf, textvariable=v, width=24 if key == "cela" else 10)
                w.grid(row=r, column=cc + 1, sticky="w", padx=2, pady=1)
                self.pvars[key] = (v, kind)
        left.columnconfigure(0, weight=1)
        left.columnconfigure(1, weight=1)
        ttk.Label(f, text=HELP_CELA, justify="left", foreground="#444", font=("TkFixedFont", 9)).pack(
            side="right", anchor="n", padx=8)

    def collect(self):
        z = self.z
        z["nazov"] = self.v_nazov.get().strip() or "Zostava"
        z["zdroj"] = self.v_zdroj.get().strip()
        z["poznamka"] = self.v_pozn.get().strip()
        if z["typ"] == "korpus":
            p = {}
            for key, (v, kind) in self.pvars.items():
                if kind == "bool":
                    p[key] = bool(v.get())
                elif kind in ("num", "edge"):
                    s = v.get().strip().replace(",", ".")
                    try:
                        f = float(s) if s else 0.0
                    except ValueError:
                        messagebox.showerror("Chyba", f"Pole '{key}' musí byť číslo.", parent=self)
                        return None
                    p[key] = int(f) if f == int(f) else f
                else:
                    p[key] = v.get().strip()
            rows, errs = engine.parse_cela(p.get("cela", ""))
            if errs:
                messagebox.showerror("Chyba v zápise čiel", "\n".join(errs), parent=self)
                return None
            z["params"] = p
        z["dielce"] = self.ed_parts.rows
        z["kovanie"] = self.ed_hw.rows
        return z


# --------------------------------------------------------------------- hlavné okno
class App(tk.Tk):
    def __init__(self, path=None):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1400x820")
        self.minsize(1000, 600)
        try:
            ttk.Style(self).theme_use("clam")
        except tk.TclError:
            pass
        self.project = engine.new_project()
        self.path = None
        self.dirty = False
        self.res = None
        self._menu()
        self._layout()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if path:
            self.open_path(path)
        self.recompute()

    # ---- UI
    def _menu(self):
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="Nová zákazka", command=self.new, accelerator="Ctrl+N")
        f.add_command(label="Otvoriť…", command=self.open, accelerator="Ctrl+O")
        f.add_command(label="Otvoriť príklad – byt Liptovská", command=self.open_example)
        f.add_separator()
        f.add_command(label="Uložiť", command=self.save, accelerator="Ctrl+S")
        f.add_command(label="Uložiť ako…", command=self.save_as)
        f.add_separator()
        f.add_command(label="Export do Excelu…", command=self.export, accelerator="Ctrl+E")
        f.add_separator()
        f.add_command(label="Koniec", command=self.on_close)
        m.add_cascade(label="Súbor", menu=f)
        n = tk.Menu(m, tearoff=0)
        n.add_command(label="Materiály a dekory…", command=self.edit_materials)
        n.add_command(label="Pravidlá výpočtu…", command=self.edit_settings)
        n.add_command(label="Názov zákazky…", command=self.rename_project)
        m.add_cascade(label="Nastavenia", menu=n)
        h = tk.Menu(m, tearoff=0)
        h.add_command(label="Návod", command=self.show_help)
        h.add_command(label="O programe", command=lambda: messagebox.showinfo(
            "O programe", f"{APP_NAME}\nverzia {engine.VERSION}\n\nVýpočet kusovníka, spotreby dosiek, hrán a kovania."))
        m.add_cascade(label="Pomoc", menu=h)
        self.config(menu=m)
        for key, fn in (("<Control-n>", self.new), ("<Control-o>", self.open), ("<Control-s>", self.save),
                        ("<Control-e>", self.export)):
            self.bind(key, lambda e, fn=fn: fn())

    def _layout(self):
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = ttk.Frame(pw, padding=6, width=400)
        pw.add(left, weight=0)
        self.lbl_project = ttk.Label(left, text="", font=("TkDefaultFont", 11, "bold"))
        self.lbl_project.pack(anchor="w")
        ttk.Label(left, text="Zostavy").pack(anchor="w", pady=(6, 0))
        self.zlist = ttk.Treeview(left, columns=("typ",), show="tree headings", height=20, selectmode="browse")
        self.zlist.heading("#0", text="Názov")
        self.zlist.heading("typ", text="Typ")
        self.zlist.column("#0", width=250)
        self.zlist.column("typ", width=130, stretch=False)
        self.zlist.pack(fill="both", expand=True)
        self.zlist.bind("<Double-1>", lambda e: self.edit_zostava())
        bf = ttk.Frame(left)
        bf.pack(fill="x", pady=4)
        for i, (txt, cmd) in enumerate((("+ Korpus", lambda: self.add_zostava("korpus")),
                                        ("+ Vlastné dielce", lambda: self.add_zostava("vlastne")),
                                        ("Upraviť", self.edit_zostava), ("Duplikovať", self.dup_zostava),
                                        ("Zmazať", self.del_zostava), ("▲", lambda: self.move(-1)),
                                        ("▼", lambda: self.move(1)))):
            ttk.Button(bf, text=txt, command=cmd).grid(row=i // 2, column=i % 2, sticky="we", padx=1, pady=1)
        for c in range(2):
            bf.columnconfigure(c, weight=1)
        ttk.Button(left, text="Export do Excelu…", command=self.export).pack(fill="x", pady=(8, 0))

        right = ttk.Frame(pw, padding=6)
        pw.add(right, weight=4)
        self.lbl_totals = ttk.Label(right, text="")
        self.lbl_totals.pack(anchor="w")
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)
        self.t_parts = self._tab("A Kusovník", [("c", "Č.", 40), ("zostava", "Zostava", 150), ("nazov", "Dielec", 210),
                                                ("mat", "Mat.", 50), ("hrubka", "Hr.", 35), ("L", "Dĺžka", 60),
                                                ("W", "Šírka", 60), ("ks", "Ks", 35), ("rL", "Rez. dĺ.", 60),
                                                ("rW", "Rez. š.", 60), ("textura", "Textúra", 110),
                                                ("D1", "D1", 35), ("D2", "D2", 35), ("S1", "Š1", 35), ("S2", "Š2", 35),
                                                ("m2", "m²", 50), ("pozn", "Poznámka", 220)])
        self.t_mat = self._tab("B Materiál", [("nazov", "Materiál", 330), ("hrubka", "Hr.", 40), ("m2", "m² čisté", 80),
                                              ("odpad", "Odpad %", 70), ("m2_odpad", "m² s odpadom", 100),
                                              ("format", "Formát", 90), ("dosky", "Dosky (plocha)", 110),
                                              ("dosky_narez", "Dosky (nárez)", 100), ("vyuzitie", "Využitie %", 80)])
        self.t_edges = self._tab("C Hrany", [("dekor", "Dekor", 250), ("hrubka", "Hrúbka", 80), ("bm", "bm čisté", 100),
                                             ("bm_prid", "bm s prídavkom", 120)])
        self.t_hw = self._tab("D Kovanie", [("polozka", "Položka", 280), ("typ", "Typ/výrobca", 280), ("ks", "Ks", 70),
                                            ("pozn", "Zostavy / poznámka", 500)])
        self.t_chk = self._tab("Kontrola", [("zostava", "Zostava", 180), ("popis", "Kontrola", 260),
                                            ("vypocet", "Výpočet", 360), ("vykres", "Výkres", 120), ("stav", "Stav", 60)])
        self.t_warn = self._tab("Varovania", [("w", "Varovanie", 1000)])
        self._plan_tab()

    def _tab(self, title, cols):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=title)
        tv = ttk.Treeview(f, columns=[c[0] for c in cols], show="headings")
        for k, lab, w in cols:
            tv.heading(k, text=lab)
            tv.column(k, width=w, anchor="w", stretch=False)
        ys = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        xs = ttk.Scrollbar(f, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        tv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="we")
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        tv._cols = [c[0] for c in cols]
        return tv

    def _plan_tab(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="Nárezový plán")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=4)
        ttk.Label(top, text="Materiál").pack(side="left")
        self.v_plan_mat = tk.StringVar()
        self.cb_plan_mat = ttk.Combobox(top, textvariable=self.v_plan_mat, state="readonly", width=50)
        self.cb_plan_mat.pack(side="left", padx=4)
        ttk.Label(top, text="Doska").pack(side="left", padx=(10, 0))
        self.v_plan_board = tk.IntVar(value=1)
        self.sp_board = ttk.Spinbox(top, from_=1, to=1, textvariable=self.v_plan_board, width=5,
                                    command=self.draw_plan)
        self.sp_board.pack(side="left", padx=4)
        self.lbl_plan = ttk.Label(top, text="")
        self.lbl_plan.pack(side="left", padx=10)
        self.cb_plan_mat.bind("<<ComboboxSelected>>", lambda e: (self.v_plan_board.set(1), self.draw_plan()))
        self.canvas = tk.Canvas(f, background="white")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw_plan())

    # ---- výpočet a zobrazenie
    def recompute(self):
        self.res = engine.compute(self.project)
        r = self.res
        self.lbl_project.config(text=self.project.get("nazov", "") + (" *" if self.dirty else ""))
        self.title(f"{APP_NAME} – {os.path.basename(self.path) if self.path else 'neuložené'}")
        self.zlist.delete(*self.zlist.get_children())
        for i, z in enumerate(self.project["zostavy"]):
            self.zlist.insert("", "end", iid=str(i), text=z.get("nazov", ""), values=(engine.TYPY.get(z["typ"], z["typ"]),))

        def fill(tv, rows):
            tv.delete(*tv.get_children())
            for row in rows:
                tv.insert("", "end", values=[row.get(k, "") for k in tv._cols])

        def e(v):
            return "–" if not v else fmt(v)
        fill(self.t_parts, [dict(x, L=fmt(x["L"]), W=fmt(x["W"]), rL=fmt(x["rL"]), rW=fmt(x["rW"]),
                                 D1=e(x["D1"]), D2=e(x["D2"]), S1=e(x["S1"]), S2=e(x["S2"]),
                                 m2=f'{x["m2"]:.2f}') for x in r["rows"]])
        fill(self.t_mat, [dict(s, m2=f'{s["m2"]:.2f}', m2_odpad=f'{s["m2_odpad"]:.2f}') for s in r["summary"]])
        fill(self.t_edges, [dict(x, hrubka=f'ABS {fmt(x["hrubka"])} mm', bm=f'{x["bm"]:.2f}',
                                 bm_prid=f'{x["bm_prid"]:.2f}') for x in r["edges"]])
        fill(self.t_hw, r["hw"])
        fill(self.t_chk, r["checks"])
        fill(self.t_warn, [{"w": w} for w in r["warnings"]] or [{"w": "Bez varovaní."}])
        self.nb.tab(5, text=f"Varovania ({len(r['warnings'])})")
        tot_m2 = sum(s["m2"] for s in r["summary"])
        self.lbl_totals.config(text=f"Dielcov: {r['totals']['dielcov']}   Kusov: {r['totals']['ks']}   "
                                    f"Plocha čistá: {tot_m2:.2f} m²   Varovania: {len(r['warnings'])}")
        mats = [f'{s["mat"]} – {s["nazov"]}' for s in r["summary"] if s["plan"]]
        self.cb_plan_mat["values"] = mats
        if mats and self.v_plan_mat.get() not in mats:
            self.v_plan_mat.set(mats[0])
        self.draw_plan()

    def draw_plan(self):
        c = self.canvas
        c.delete("all")
        if not self.res:
            return
        sel = self.v_plan_mat.get().split(" – ")[0]
        s = next((x for x in self.res["summary"] if x["mat"] == sel and x["plan"]), None)
        if not s:
            return
        nb = len(s["plan"])
        self.sp_board.config(to=nb)
        try:
            bi = max(1, min(nb, int(self.v_plan_board.get())))
        except (tk.TclError, ValueError):
            bi = 1
        m = self.project_material(sel)
        BL, BW = float(m["dl"]), float(m["sir"])
        cw, ch = max(c.winfo_width(), 200), max(c.winfo_height(), 150)
        k = min((cw - 40) / BL, (ch - 40) / BW)
        ox, oy = 20, 20
        c.create_rectangle(ox, oy, ox + BL * k, oy + BW * k, fill="#f3efe2", outline="#555")
        for (x, y, w, h, popis, rot) in s["plan"][bi - 1]:
            x0, y0 = ox + x * k, oy + y * k
            c.create_rectangle(x0, y0, x0 + w * k, y0 + h * k, fill="#d9cfa8", outline="#5b5b3a")
            if w * k > 40 and h * k > 14:
                c.create_text(x0 + 3, y0 + 2, anchor="nw", text=f"{fmt(w)}×{fmt(h)}", font=("TkDefaultFont", 8))
            if w * k > 90 and h * k > 28:
                c.create_text(x0 + 3, y0 + 14, anchor="nw", text=popis.split(" / ")[-1][:int(w * k / 6)],
                              font=("TkDefaultFont", 7), fill="#333")
        self.lbl_plan.config(text=f"Dosiek: {nb}   Využitie: {s['vyuzitie']} %   Formát {s['format']} "
                                  f"(textúra {'áno' if m.get('textura') else 'nie'})")

    def project_material(self, kod):
        return next((m for m in self.project["materialy"] if m["kod"] == kod), {"dl": 2800, "sir": 2070})

    def mark(self):
        self.dirty = True
        self.recompute()

    # ---- zostavy
    def _sel(self):
        s = self.zlist.selection()
        return int(s[0]) if s else None

    def mat_codes(self):
        return [m["kod"] for m in self.project["materialy"]]

    def add_zostava(self, typ):
        z = engine.new_zostava(typ)
        codes = self.mat_codes()
        if typ == "korpus":
            for k in ("mat_korpus", "mat_cela", "mat_chrbat", "mat_dno_zasuviek"):
                if z["params"][k] not in codes and codes:
                    z["params"][k] = codes[0]
        r = ZostavaDialog(self, z, codes).run()
        if r:
            self.project["zostavy"].append(r)
            self.mark()
            self.zlist.selection_set(str(len(self.project["zostavy"]) - 1))

    def edit_zostava(self):
        i = self._sel()
        if i is None:
            return
        r = ZostavaDialog(self, self.project["zostavy"][i], self.mat_codes()).run()
        if r:
            self.project["zostavy"][i] = r
            self.mark()
            self.zlist.selection_set(str(i))

    def dup_zostava(self):
        i = self._sel()
        if i is None:
            return
        z = copy.deepcopy(self.project["zostavy"][i])
        z["nazov"] += " (kópia)"
        self.project["zostavy"].insert(i + 1, z)
        self.mark()
        self.zlist.selection_set(str(i + 1))

    def del_zostava(self):
        i = self._sel()
        if i is None:
            return
        if messagebox.askyesno("Zmazať", f"Zmazať zostavu „{self.project['zostavy'][i]['nazov']}“?"):
            del self.project["zostavy"][i]
            self.mark()

    def move(self, d):
        i = self._sel()
        if i is None:
            return
        j = i + d
        zs = self.project["zostavy"]
        if 0 <= j < len(zs):
            zs[i], zs[j] = zs[j], zs[i]
            self.mark()
            self.zlist.selection_set(str(j))

    # ---- nastavenia
    def edit_materials(self):
        r = ListDialog(self, "Materiály a dekory", MAT_COLS, self.project["materialy"],
                       hint="Kód sa používa v dielcoch. Formát 0 = bez nárezového plánu (napr. ohýbané diely). "
                            "Textúra áno = dielce sa neotáčajú, dĺžka dielca ide pozdĺž dĺžky dosky.").run()
        if r is not None:
            codes = [m["kod"] for m in r]
            if len(codes) != len(set(codes)) or "" in codes:
                messagebox.showerror("Chyba", "Kódy materiálov musia byť vyplnené a jedinečné.")
                return
            self.project["materialy"] = r
            self.mark()

    def edit_settings(self):
        r = SettingsDialog(self, self.project.get("nastavenia", {})).run()
        if r:
            self.project["nastavenia"] = r
            self.mark()

    def rename_project(self):
        d = ModalDialog(self, "Názov zákazky", "420x120")
        v = tk.StringVar(value=self.project.get("nazov", ""))
        ttk.Entry(d.body, textvariable=v, width=50).pack(fill="x")
        d.collect = lambda: v.get().strip() or "Zákazka"
        r = d.run()
        if r:
            self.project["nazov"] = r
            self.mark()

    # ---- súbory
    def confirm_discard(self):
        if not self.dirty:
            return True
        a = messagebox.askyesnocancel("Neuložené zmeny", "Uložiť zmeny v aktuálnej zákazke?")
        if a is None:
            return False
        if a:
            return self.save()
        return True

    def new(self):
        if self.confirm_discard():
            self.project, self.path, self.dirty = engine.new_project(), None, False
            self.recompute()

    def open(self):
        if not self.confirm_discard():
            return
        p = filedialog.askopenfilename(filetypes=FILE_TYPES)
        if p:
            self.open_path(p)

    def open_example(self):
        if self.confirm_discard():
            self.open_path(resource_path("priklady", "liptovska.nkp"), as_template=True)

    def open_path(self, p, as_template=False):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if "zostavy" not in data:
                raise ValueError("Súbor nie je projekt kalkulátora.")
            data.setdefault("nastavenia", dict(engine.DEFAULT_SETTINGS))
            data.setdefault("materialy", copy.deepcopy(engine.DEFAULT_MATERIALS))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Chyba pri otváraní", str(e))
            return
        self.project = data
        self.path = None if as_template else p
        self.dirty = False
        self.recompute()

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.project, f, ensure_ascii=False, indent=1)
        except OSError as e:
            messagebox.showerror("Chyba pri ukladaní", str(e))
            return False
        self.dirty = False
        self.recompute()
        return True

    def save_as(self):
        p = filedialog.asksaveasfilename(defaultextension=".nkp", filetypes=FILE_TYPES,
                                         initialfile=(self.project.get("nazov") or "zakazka") + ".nkp")
        if not p:
            return False
        self.path = p
        return self.save()

    def export(self):
        p = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                                         initialfile=(self.project.get("nazov") or "zakazka") + "_spotreba.xlsx")
        if not p:
            return
        try:
            export_xlsx(self.project, self.res, p)
        except OSError as e:
            messagebox.showerror("Chyba exportu", f"{e}\n\nNie je súbor otvorený v Exceli?")
            return
        messagebox.showinfo("Export", f"Uložené:\n{p}")

    def show_help(self):
        d = tk.Toplevel(self)
        d.title("Návod")
        d.geometry("760x600")
        t = tk.Text(d, wrap="word", padx=10, pady=10)
        t.pack(fill="both", expand=True)
        t.insert("1.0", HELP_TEXT)
        t.config(state="disabled")

    def on_close(self):
        if self.confirm_discard():
            self.destroy()


HELP_TEXT = """KALKULÁTOR SPOTREBY MATERIÁLU – NÁVOD

1. Zákazka
   Súbor → Nová zákazka. Názov zmeníte v Nastavenia → Názov zákazky.
   Príklad: Súbor → Otvoriť príklad – byt Liptovská.

2. Materiály
   Nastavenia → Materiály a dekory. Ku každému materiálu zadáte kód (napr. U16), názov,
   hrúbku, či má textúru (letokruh), dekor hrany, formát dosky a % odpadu.

3. Zostavy
   + Korpus – parametrická skrinka: rozmery, sokel, vrch (strop/spojky), počet sekcií,
     nadstavec, police, tyče, chrbát (HDF / DTD vložený), čelá a otváranie.
     Program vygeneruje dielce, rezné rozmery, hrany a kovanie (pánty Blum podľa výšky dvierok,
     LEGRABOX podľa výšky čela a hĺbky, úchytky, nosiče políc, nožičky, závesy, konfirmáty).
   + Vlastné dielce – ľubovoľné dielce zadané ručne (oblúky, atypy, pracovné dosky…).
   Každá zostava má aj záložky „Dielce navyše“ a „Kovanie navyše“.

4. Zápis čiel (zdola nahor, oddelené ;)
""" + HELP_CELA + """

5. Hrany
   D1, D2 = dlhé hrany (pozdĺž dĺžky), Š1, Š2 = krátke hrany. Hodnota = hrúbka ABS v mm (0 = bez).
   Rezný rozmer = hotový rozmer − hrúbky hrán. Pri tvarových dielcoch vyplňte „Hrana dĺžka (tvar)“.

6. Výsledky
   A Kusovník, B Materiál (počet dosiek podľa plochy s odpadom aj podľa nárezového plánu),
   C Hrany (+ prídavok), D Kovanie, Kontrola rozmerov, Varovania, Nárezový plán (náhľad).
   Súbor → Export do Excelu uloží všetko do .xlsx.

7. Upozornenie
   Nárezový plán je orientačný (gilotínový odhad). Rozmery zásuviek overte v Blum DYNAPLAN
   a všetky rozmery zamerajte na mieste.
"""


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    App(path).mainloop()
