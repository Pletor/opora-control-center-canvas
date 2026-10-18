Brány cyklu v detailu fragmentu Schránky, **jen zobrazení** (kontrakt `docs/schranka-neurony.md` §3, §5, §6 a §9 body 4, 8, 9, 12). Kód ho provádí, nemění. Schránku řídí agenti přes API (`op: propose`, `op: gate`, `confirm-lesson` …); člověk tu vidí, kde cyklus je a kdo co udělal. Žádný přepínač, formulář ani tlačítko toku.

**Kdo to skládá.** `BriefVaultDock` vloží `FragmentGates` do akcí detailu fragmentu (`BriefVaultPanel` → `FragmentDetailView` předá načtený detail).

**Dílky** (`components/`)

- `FragmentGates.tsx` — rodič: osm bran (`gateRows`), věta o slepé uličce (důvod z `gateDetail.decided`) a o zneplatnění, stav fronty agentů disciplíny z `GET /api/brief-vault/next` (další fragment a brána, `needs`, počet `blocked`). Poslední návrh každé brány bere z `proposals` detailu fragmentu (`GET /api/brief-vault/fragment`) a předá ho řádku brány.
- `GateRow.tsx` — jedna brána (u Mikrokroku číslovaný seznam `steps` a štítek vrstvy `layer`): tečka (`brief-gates__dot`, stejný jazyk jako pruh ve stromu), titulek, „potvrdil agent/člověk X · kdy“ (`by`, `actor`, `at` záznamu), payload česky (`payloadLines`), chyba předpovědi u Ověřeno, poslední návrh brány s autorem a stavem (`proposalStatus`: čeká na potvrzení / použit / zamítl kdo a proč / neplatí po vypnutí brány; payload jen u nepoužitého) a proč stojí.
- `DisciplineLessons.tsx` — `GET /api/brief-vault/lessons?discipline`: druh, text, platná váha v % a autor.

**Logika** (`logic/`, test vedle)

- `gate-view.ts` — `roundLine` / `blockReason` (kolo N/3, „vyčerpáno – čeká na člověka“, krátký důvod čekání), rozpad `blockedBy` ve `queueText`, `payloadLines`, `whoLabel`, `proposalStatus`, `gateRows` (zapnutá / zneplatněná / další na řadě / proč stojí), `deadEndReason`, tvar odpovědi `/next` a `queueText`.

Titulky bran a pruh teček ve stromu jsou sdílené v `frontend/editor/node-detail/brief-vault/logic/gate-bar.ts`. Jednorázové nastavení „Povolit kontrolu bran Jev pro projekt“ je mimo tok, v Přehledu Schránky (`../components/JevGateCheckSetting.tsx`).

**Styl**

`styles/fragment-gates.css`, blok `fragment-gates` s příběhovým komentářem.
