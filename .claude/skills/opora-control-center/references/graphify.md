# Graphify — původní CLI a původní HTML

Zdroj: https://github.com/Graphify-Labs/graphify
Runtime: oficiální distribuce `graphifyy==0.9.24` (MIT), oddělená od FastAPI venv.
Nejde o vlastní extraktor, převodník ručních uzlů ani renderer.

## Obsluha

Projekt → **Graphify-out** načte `graphify-out/graph.html` hlavního projektu.
Generování běží samo: když stabilní sada v projektu chybí a po každém mergi do
main (automatika, `map-refresh.md`, `docs/mapy-projektu.md`). **Aktualizovat
graf → Aktualizovat teď** ho spustí hned nad aktuálním zdrojovým kódem, i při
„Pouze ručně“. Otevření mapy samo nic negeneruje.
Zdroj vlastní projektový hub, worktree se stejně jako u Archify přeloží na hlavní
pracovní strom. Browser neposílá cestu, shell příkaz ani nastavení modelu.
Ruční uzly Editoru nejsou importovány, upraveny ani odstraněny.

## Původní příkazy

Adaptér volá původní modul `python -m graphify`, ekvivalent:

```text
graphify extract <hlavní-projekt> --code-only --max-workers 2 --out <dočasný-výstup>
graphify cluster-only <dočasný-výstup> --no-label
```

V této verzi `extract` vytvoří graf JSON a analýzu, nikoli HTML/report.
Druhý původní příkaz vytvoří HTML a report; `--no-label` zakazuje modelové
pojmenování komunit. Názvy typu Community N jsou tedy záměrné, ne chyba rendereru.
Neanalyzují se dokumenty/média. `.graphifyignore` vyřazuje vendor, cache,
generované soubory a agentní pracovní data. Graphify sám vyřazuje citlivé soubory.
Nativní varování o souborech bez uzlů jsou uvedena v metadatech zobrazení.
Výsledek není živě aktualizovaný ani úplný sémantický model celého projektu.

## Runtime na dalším stroji

```text
uv venv .venv-graphify
uv pip install --python .venv-graphify/Scripts/python.exe graphifyy==0.9.24
```

Na Unixu použijte `.venv-graphify/bin/python`. Volitelně nastavte
`OPORA_GRAPHIFY_PYTHON` na absolutní cestu již nainstalovaného interpretru.
Bez nastavení adaptér ověřuje projektovou `.venv-graphify`, Python na PATH a
interpreter serveru. Verze je ověřena; žádný request automaticky nic neinstaluje.
Po změně runtime restartujte server (výběr je cachovaný).

## Omezení adaptéru

- Původní `detect` ověří 1–500 zdrojových souborů / 32 MiB; pro větší projekt
  upravte jeho `.graphifyignore`. Běh má 120 s a 2 AST procesy.
- API klíče, tokeny a PYTHONPATH se do podprocesu nepředávají. Na Windows musí
  zůstat USERPROFILE/HOMEDRIVE/HOMEPATH pro `Path.home()`. `-I -X utf8` brání
  importům z projektu a chybám kódování logu.
- Windows Job Object ukončuje i potomky. Opakované kliknutí nevytváří souběžné běhy;
  OS zámek chrání projekt i mezi procesy, obvyklý server běží s jedním workerem.
- Teprve po úspěchu se zveřejní přesné původní bajty `graph.html`, `graph.json`,
  `GRAPH_REPORT.md`; `opora-receipt.json` dokládá verzi, čas, rozsah a SHA-256.
  Ruční i automatický běh zapisují tutéž sadu v `graphify-out/` přes
  `<name>.tmp` a `os.replace`. Chyba extrakce před publikací nemění předchozí výstupy.
- Viewer přidává CSP jen do náhledu a používá iframe bez same-origin oprávnění.
  Původní HTML načítá vis-network 9.1.6 z unpkg.com; nejde o plně offline viewer.
  Jeho JSON/HTML downloady jsou beze změny. Graf se nepřevádí do React Flow.
- Náhled není OS sandbox pro nepřátelský lokální účet přepisující soubory během běhu.

## Kód a ověření

`backend/api/project/graphify_routes.py`, `backend/project/maps/graphify_{runtime,worker}.py`, `frontend/project/maps/components/GraphifyMap.tsx`.
Navigace i geometrie zůstávají ve společném `ProjectLayout`.
API: GET `/api/graphify/artifact?project=ID`, POST `/api/graphify/generate?project=ID`.
POST vyžaduje stejný Origin a `Content-Type: application/json`.
Test: `pytest backend/api/project/test_graphify_routes.py` (nativní smoke vyžaduje runtime výše).
E2E testy byly odstraněny při restrukturalizaci; ověření proveď ručně přes náhled (`tools/serve-preview.py`) nebo přes API.
Testovací fixture HTML není důkaz nasazení; skutečný náhled je ověřován zvlášť.
