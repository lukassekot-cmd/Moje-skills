"""Jednoduchý gilotínový nárezový plán (odhad počtu dosiek).

Nie je to optimalizátor ako v profesionálnych programoch – dáva realistický horný odhad
počtu dosiek pri rešpektovaní smeru textúry, hrúbky rezu a orezu okraja.
"""


def _fits(fw, fh, w, h):
    return w <= fw + 1e-6 and h <= fh + 1e-6


def nest_material(pieces, board_l, board_w, grain, kerf=4.0, trim=10.0):
    """pieces: [(L, W, ks, popis)] – L je v smere textúry (pozdĺž dĺžky dosky).
    Vráti {'dosky': n, 'vyuzitie': %, 'nezmestia': [...], 'plan': [[(x, y, l, w, popis, otocene), ...], ...]}"""
    BL, BW = board_l - 2 * trim, board_w - 2 * trim
    items, bad = [], []
    for L, W, ks, popis in pieces:
        L, W = float(L), float(W)
        ok = _fits(BL, BW, L, W) or (not grain and _fits(BL, BW, W, L))
        if not ok:
            bad.append(f"{popis} {L:g}×{W:g}")
            continue
        for _ in range(int(ks)):
            items.append((L, W, popis))
    items.sort(key=lambda it: (max(it[0], it[1]), it[0] * it[1]), reverse=True)

    boards = []  # každá doska: {'free': [(x,y,w,h)], 'placed': [...]}

    def place(board, L, W, popis):
        best = None
        for i, (fx, fy, fw, fh) in enumerate(board["free"]):
            for rot in ((False,) if grain else (False, True)):
                w, h = (W, L) if rot else (L, W)
                if _fits(fw, fh, w, h):
                    score = min(fw - w, fh - h)
                    if best is None or score < best[0]:
                        best = (score, i, rot, w, h)
        if best is None:
            return False
        _, i, rot, w, h = best
        fx, fy, fw, fh = board["free"].pop(i)
        board["placed"].append((fx + trim, fy + trim, w, h, popis, rot))
        rw, rh = fw - w - kerf, fh - h - kerf
        # gilotínové delenie – kratší zvyšok sa oddelí
        if rw * fh > fw * rh:
            if rw > 0:
                board["free"].append((fx + w + kerf, fy, rw, fh))
            if rh > 0:
                board["free"].append((fx, fy + h + kerf, w, rh))
        else:
            if rh > 0:
                board["free"].append((fx, fy + h + kerf, fw, rh))
            if rw > 0:
                board["free"].append((fx + w + kerf, fy, rw, h))
        return True

    for L, W, popis in items:
        for b in boards:
            if place(b, L, W, popis):
                break
        else:
            b = {"free": [(0.0, 0.0, BL, BW)], "placed": []}
            boards.append(b)
            place(b, L, W, popis)

    used = sum(w * h for b in boards for (_, _, w, h, _, _) in b["placed"])
    total = len(boards) * board_l * board_w
    return {"dosky": len(boards), "vyuzitie": round(100 * used / total, 1) if total else 0.0,
            "nezmestia": bad, "plan": [b["placed"] for b in boards]}
