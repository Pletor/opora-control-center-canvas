Brány cyklu v detailu fragmentu Schránky, **jen zobrazení** (kontrakt `docs/schranka-neurony.md` §3, §5, §6 a §9 body 4, 8, 9, 12). Kód ho provádí, nemění. Schránku řídí agenti přes API (`op: propose`, `op: gate`, `confirm-lesson` …); člověk tu vidí, kde cyklus je a kdo co udělal. Žádný přepínač, formulář ani tlačítko toku.

**Kdo to skládá.** `BriefVaultDock` vloží `FragmentGates` do akcí detailu fragmentu (`BriefVaultPanel` → `FragmentDetailView` předá načtený detail).

**Dílky** (`components/`)

- `FragmentGates.tsx` — rodič: osm bran (`gateRows`), věta o slepé uličce (důvod z `gateDetail.decided`) a o zneplatnění, stav fronty agentů disciplíny z `GET /api/brief-vault/next` (další fragment a brána, `needs`, počet `blocked`). Návrh čekající na potvrzení backend v detailu nevrací; ukáže se jen ten, který fronta vrací pro tento fragment.
- `GateRow.tsx` — jedna brána: tečka (`brief-gates__dot`, stejný jazyk jako pruh ve stromu), titulek, „potvrdil agent/člověk X · kdy“ (`by`, `actor`, `at` záznamu), payload česky (`payloadLines`), chyba předpovědi u Ověřeno, u další brány na řadě návrh s autorem („navrhl …“) a proč stojí.
- `DisciplineLessons.tsx` — `GET /api/brief-vault/lessons?discipline`: druh, text, platná váha v % a autor.

**Logika** (`logic/`, test vedle)

- `gate-view.ts` — `payloadLines`, `whoLabel`, `gateRows` (zapnutá / zneplatněná / další na řadě / proč stojí), `deadEndReason`, tvar odpovědi `/next` a `queueText`.

Titulky bran a pruh teček ve stromu jsou sdílené v `frontend/editor/node-detail/brief-vault/logic/gate-bar.ts`. Jednorázové nastavení „Povolit kontrolu bran Jev pro projekt“ je mimo tok, v Přehledu Schránky (`../components/JevGateCheckSetting.tsx`).

**Styl**

`styles/fragment-gates.css`, blok `fragment-gates` s příběhovým komentářem.
