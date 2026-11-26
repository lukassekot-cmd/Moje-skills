# Kalkulátor spotreby materiálu – korpusový nábytok

Desktopový program pre Windows (funguje aj na macOS a Linuxe), ktorý z parametrov skriniek
alebo z ručne zadaných dielcov vypočíta:

- **A) kusovník** – hotové aj rezné rozmery (po odpočte hrán), materiál, textúra, hrany D1/D2/Š1/Š2,
- **B) spotrebu dosiek** – m² čisté, m² s odpadom, počet dosiek podľa plochy aj podľa nárezového plánu,
- **C) hrany** – bm podľa dekoru a hrúbky, s prídavkom,
- **D) kovanie** – pánty Blum podľa výšky dvierok, LEGRABOX podľa výšky čela a hĺbky, úchytky,
  nosiče políc, nožičky, závesy, tyče, konfirmáty a skryté spoje,
- **kontrolu rozmerov** a **varovania** (dielec väčší ako formát, chybný zápis čiel…),
- **nárezový plán** (grafický náhľad dosiek),
- **export do Excelu** (.xlsx).

## Inštalácia na Windows

1. V repozitári na GitHube otvorte **Actions → „Kalkulátor – Windows build“** a vyberte posledný úspešný beh.
2. Dole v časti **Artifacts** stiahnite **Kalkulator-Windows** (zip).
3. Rozbaľte zip a spustite **Kalkulator_instalator.exe** – vytvorí ikonu v ponuke Štart (voliteľne aj na ploche)
   a priradí súbory projektov `.nkp`.
   - Prípadne stačí spustiť **Kalkulator.exe** priamo, bez inštalácie.
   - Windows SmartScreen môže upozorniť na nepodpísaný program: „Ďalšie informácie → Spustiť aj tak“.

### Alternatíva – zo zdrojových súborov

- Windows: nainštalujte Python 3.10+ z python.org a spustite `spustit.bat`.
  Vlastné `.exe` zostavíte cez `build_windows.bat` (výsledok `dist\Kalkulator.exe`).
- macOS / Linux: `./spustit.sh` (potrebný Python s Tkinter).

## Práca s programom

1. **Súbor → Nová zákazka** (alebo **Otvoriť príklad – byt Liptovská**).
2. **Nastavenia → Materiály a dekory** – kód, názov, hrúbka, textúra, dekor hrany, formát dosky, % odpadu.
3. **+ Korpus** – parametrická skrinka:
   rozmery, sokel, vrch (strop/spojky), dno, sekcie, nadstavec, police, tyče, chrbát (HDF / DTD vložený),
   čelá, typ čiel (naložené/vložené), otváranie (úchytka / push / podhmat).
4. **+ Vlastné dielce** – atypické dielce zadané ručne (oblúky, pracovné dosky, blendy…).
   Každá zostava má aj záložky **Dielce navyše** a **Kovanie navyše**.
5. Výsledky sa prepočítavajú okamžite. **Súbor → Export do Excelu** uloží všetky tabuľky.

### Zápis čiel (zdola nahor, oddelené `;`)

| Zápis | Význam |
|---|---|
| `D2` | 2 dvierka vedľa seba, výška = zvyšok |
| `D3 470` | 3 dvierka v zóne 470 mm |
| `Z 250` | zásuvka, zóna 250 mm |
| `Z2 200` | 2 zásuvky vedľa seba |
| `O 300` | otvorená zóna |
| `B 100` | pevná blenda |

Príklady: kuchynská zásuvková `Z 390; Z`, šatník s nadstavcom `D3; D3 470`.

### Pravidlá výpočtu (dajú sa zmeniť v Nastavenia → Pravidlá výpočtu)

- škára naložených čiel 3 mm, vložených 2 mm po obvode,
- rezný rozmer = hotový − hrúbky hrán, prídavok na hrany 10 %,
- pánty: do 900 mm 2 ks, do 1600 mm 3 ks, do 2000 mm 4 ks, nad 5 ks,
- LEGRABOX: výška podľa čela (N < 120, M < 160, K < 200, C < 260, inak F), NL podľa hĺbky,
  dno zásuvky (LW − 35) × (NL − 10),
- nárezový plán: gilotínový odhad s rezom 4 mm a orezom 10 mm, rešpektuje textúru.

> Nárezový plán je orientačný. Rozmery zásuviek overte v Blum DYNAPLAN a rozmery zamerajte na mieste.

## Vývoj

```
pip install -r requirements.txt pytest
python -m pytest -q tests
python main.py
```
