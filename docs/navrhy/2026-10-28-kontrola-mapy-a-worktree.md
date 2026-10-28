# Kontrola mapy vidí worktree – návrh (gap 9)

Stav: návrh, ne kontrakt. Kód zatím nic z toho neprovádí; čeká na rozhodnutí člověka (§6).

## 1. Problém

`map_check` (`backend/project/architecture/map_check.py`) počítá díry nad `architecture_graph`
(`work_status.py`): u Git projektu je to architektura složená s obsahem **`main`**. Komponenty, které agent
staví ve worktree, kontrola nevidí, dokud se worktree nesloučí. Důsledky:

- agent ve worktree `w` dostane v `holes` (brief) a `mapGaps` (agent-state) díru, kterou už ve `w` zalepil
  (typicky `section.unrealized`, `command.no-receiver`, `edge.carries-unset`);
- dva agenti ve dvou worktree vezmou tutéž díru z `mapGaps`, protože fronta neví, že na ní už někdo pracuje;
- dávka plánu (N3, `canvas_plan_map_check`) to nemá: počítá nad grafem prostoru, do kterého zapisuje.
  Kontrola mapy a dávka se tedy u worktree rozcházejí.

## 2. Cíl

Díra mapy má tři stavy místo dvou: **otevřená** (na mainu i ve všech worktree), **v práci** (na mainu ano,
v některém worktree už ne) a **nová ve worktree** (na mainu není, worktree ji způsobil). Pravda zůstává main;
worktree jen doplňuje, kdo na díře pracuje.

## 3. Návrh

1. `check_map` se nemění (čistá funkce nad grafem).
2. `map_check(service, project, locate, workspace=None)`: s `workspace` počítá nad `service.view(project, wid)`
   (architektura ∪ obsah worktree, stejné skládání jako `/api/view`). `GET …/map-check?workspace=<wid>`.
3. Souhrn přes aktivní worktree (`work-status` je zná): `map_check_overlay(service, project)` spočte main a každý
   aktivní worktree, nálezy páruje podle `(rule, nodeId|edgeId|journeyId, message)` a každému nálezu mainu přidá
   `closedIn: [wid…]`. Nálezy jen ve worktree vrátí zvlášť jako `openedIn: {wid: [nález…]}`.
   Výsledek se drží v paměti podle digestu pohledů (nový výpočet jen při změně grafu worktree).
4. Agent-state `mapGaps`: díra s neprázdným `closedIn` dostane `inProgress: {workspaceId}` a do fronty volné práce
   se nepočítá (agent ji vidí, ale nebere). Brief karty ve worktree `w` počítá `holes` nad pohledem `w`.
5. Velín (řádek „Díry mapy pro agenty“) ukáže „218 · 12 v práci“; Studio odznak díry zůstává podle mainu.
6. Strážce `mapa` dál hlídá main (pravda pro trend); `openedIn` se do strážců nepropisuje, řeší ho dávka (N3).

## 4. Co se nemění

Žádná nová tabulka ani změna schématu, žádný zápis, žádné LLM. `journey.*` pravidla zůstávají nad mainem
(doklady cest jsou projektové, `latest_journey_runs`). Lokální projekt (`draft`) nemá worktree, výstup beze změny.

## 5. Cena

Kontrola mapy je čistá funkce v řádu milisekund až desítek ms na graf; při N aktivních worktree je to N + 1
skládání pohledu. Cache podle digestu drží cenu u nečinných worktree na nule.

## 6. Otázky pro člověka

1. Má se díra „v práci“ úplně skrýt z fronty `mapGaps`, nebo zůstat se značkou a agent ji smí vzít taky?
2. Má velín ukazovat i „nové díry ve worktree“ (`openedIn`), nebo to nechat jen na dávce plánu a review?
3. Stavět jako jedno PR (backend + agent-state + velín), nebo backend zvlášť?
