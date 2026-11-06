# Linie L3 – detail commitu: od tečky k plánu, kartě a kanceláři

Datum: 2026-11-06. Navazuje na L2 (`2026-11-06-linie-editor-a-vynuceni.md`). Stav: první průchod.

## Proč

Člověk vidí v Git grafu 13 teček a nerozumí jim. Tečka je důkaz, ne vysvětlení. Chce z ní otevřít detail,
kde uvidí **co se tvoří** (náhled / artefakt), **podle jakého plánu a proč** (ticket, karta na plátně, kroky plánu),
**kdo na tom pracuje** (kancelář: dělník, relace brány, Pletor a srdce jako zadavatelé) a **kam v linii to patří**
(kulička, stav, další krok). Stejná data dávají Pletorovi rychlý přehled jednou větou a srdci podklad k rozkreslení
do plánu.

## Co existuje (inventura)

- Commity větve čte `backend/agi_pletor/linie/graph.py` (`sha`, `sha7`, `title`, `parents`, `at`).
- Ticket nese `machine.cardId`, `machine.executionId`, `sessionId`, `delivery`, `work` (`database/repositories/tickets.py`
  `public()`); kancelář = `gate_sessions` (`worker_name`, `role`, `workspace_id`), zadavatel = `machine.department` /
  `machine.profile`.
- Plán karty = `spec.steps` ve `fields` přijaté specifikace (`backend/canvas/opora_plan_steps.py`), kroky zafixované
  pro exekuci v `execution.assignment.steps`.
- Odkaz na kartu: `?project&workspace&screen=canvas&node=<id>&ohCard=<id>&ohTab=steps` (`App.tsx`, `card-drawer-store.ts`).
- Commit se ke kartě hlásí trailerem `Opora-Node: <nodeId>` (`backend/canvas/commit_pairs.py`), k exekuci
  `Opora-Execution:` (PR body).
- Detail ticketu ve Velínu už je `LinieDetail.tsx` (Zadání, Větev a revize, Commity, PR, Kontroly, Přijetí).

## Kontrakt

### API `GET /api/pletor/linie/commit/{sha}?project&workspace` (člověk i agent, čtení)

```json
{
  "commit": {"sha": "…", "sha7": "2522dc8", "title": "fix(pletor): …", "body": "…", "at": "2026-11-06T13:42:00Z",
             "author": "Pletor", "files": 3, "stat": "3 files changed, …", "branches": ["feat/velin-linie"],
             "trailers": {"node": "hero" | null, "execution": "ex_…" | null}},
  "ticket": {"ticketId": "tk_…", "state": "open", "stateLabel": "otevřeno", "next": "…",
             "body": {"essence": "…", "build": "…", "doneCriteria": ["…"]},
             "work": {"branch": "…", "headSha": "…", "target": "…", "preview": {...} | null},
             "card": {"id": "hero", "name": "Hero sekce", "link": "/?project=…&screen=canvas&node=hero&ohCard=hero&ohTab=steps"} | null,
             "office": {"worker": "office-1", "role": "worker", "department": "…", "profile": "…", "executionId": "ex_…"} | null,
             "plan": [{"id": "s1", "order": 1, "title": "…", "acceptance": "…", "kind": "code"}]} | null,
  "pr": {"number": 350, "state": "OPEN", "url": "…"} | null,
  "preview": {"url": "http://127.0.0.1:8790/…", "state": "running", "sha": "…"} | null,
  "sentence": "Commit 2522dc8 na feat/velin-linie: fix(pletor): … Bez evidovaného plánu (žádný ticket)."
}
```

Pravidla:
1. **Ticket se hledá podle větve a rozsahu**: ticket s `work.branch`, která commit obsahuje (`merge-base --is-ancestor`),
   a commit není předkem `work.baseSha`. Víc ticketů → nejnovější. Trailer `Opora-Node` má přednost jako `card`.
2. **Bez ticketu se nic nevymýšlí**: `ticket: null` a věta „bez evidovaného plánu“. To je pravdivý stav práce mimo proces
   (dnešních 13 commitů z terminálu vznikne přesně takto).
3. `card.link` vede na plátno projektu s otevřeným detailem karty na záložce kroků. `plan` jsou kroky `spec.steps`
   přijaté specifikace karty (přes `service.view(pid, wid)["graph"]`), seřazené `order`.
4. `office` = relace brány ticketu (`sessionId` → `gate_sessions`) + `machine.department/profile/executionId`.
   Bez relace `office: null`.
5. `preview` = běžící náhled větve z registru náhledů (`previews.status`), jen pokud jeho `sha` je commit nebo jeho potomek.
6. Čtení gitu jen přes `integrations.gitio.git`; neznámé sha → 404 `commit_not_found`.

### Velín: panel detailu commitu (`LinieCommit.tsx`)

- Klik na tečku v Git grafu (i Enter na ní) otevře panel vpravo místo karty MAIN; Esc / „Zavřít“ vrátí MAIN.
- Čtyři vrstvy shora, v pořadí záměr → kdo → co → kde:
  1. **Proč** – název karty s odkazem „otevřít na plátně“, `essence` / `build` / kritéria, kroky plánu (hotové nijak
     neoznačuje – průběh kroků není v této verzi).
  2. **Kdo** – dělník a role, oddělení/profil, exekuce; bez relace text „kancelář neevidována“.
  3. **Co** – zpráva commitu, soubory a stat, větve, PR, tlačítko „Otevřít náhled“ (jen s běžícím náhledem).
  4. **Kde v linii** – kulička (klik otevře `LinieDetail`), stav, další krok.
- Bez ticketu panel ukáže vrstvu 3 a zřetelně „bez evidovaného plánu“; nic se nepředstírá.
- Věta `sentence` jde i Pletorovi (stejná jako v panelu nahoře).

## Ověření

- Backend test: commit s ticketem → `ticket`, `card`, `office`, `plan`; commit mimo ticket → `ticket: null`;
  neznámé sha → 404; trailer `Opora-Node` → `card`.
- Frontend test logiky (`linie-commit.test.ts`): pohled z JSON, bezpečné prázdné hodnoty, věta.
- Kouřově v náhledu 8790: klik na tečku 2522dc8 → panel „bez evidovaného plánu“, soubory a PR #350.

## Mimo rozsah (další krok)

Průběh kroků plánu (`opora_step_results`), rozkreslení commitu srdcem do plánu, commit → artefakt mimo náhled
(screenshot, deník), více ticketů na jedné větvi.
