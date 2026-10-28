# Kontrola mapy vidí worktree (gap 9)

Stav: **kontrakt**, rozhodnutí uživatele 2026-10-28 (§6). Kód ho provádí, nemění.

## 1. Problém

`map_check` (`backend/project/architecture/map_check.py`) počítá díry nad `architecture_graph`
(`work_status.py`): u Git projektu je to architektura složená s obsahem **`main`**. Komponenty, které agent
staví ve worktree, kontrola nevidí, dokud se worktree nesloučí. Agent ve worktree proto dostává díry, které už
zalepil, dva agenti berou tutéž díru a člověk nevidí, jaké nové díry práce ve worktree cestou otevírá.

## 2. Cíl

Díra mapy má tři stavy: **otevřená** (na mainu i ve všech worktree), **v práci** (na mainu ano, v některém
aktivním worktree už ne) a **nová ve worktree** (na mainu není, worktree ji způsobil). Pravda zůstává main;
worktree doplňuje, kdo na čem pracuje a kam práce míří. Člověk to musí vidět průběžně, protože nové díry
mohou změnit směr práce.

## 3. Jeden zdroj: `map_check_worktrees.py`

Samostatný modul `backend/project/architecture/map_check_worktrees.py` je **jediné místo**, které skládá kontrolu
mapy přes worktree. Agent-state, brief, velín i Studio čtou jeho výsledek; nikdo jiný worktree nekontroluje.

- `worktree_overlay(service, project)` → 
  `{main: [nález…], worktrees: [{workspaceId, branch, actor, domainId, closed: [klíč…], opened: [nález…]}]}`.
  `main` = `check_map(architecture_graph, runs, locate=True)["findings"]`. Pro každý **aktivní** worktree
  (řádky `workspaces` Git projektu mimo `main`, ne archivované) `check_map(service.view(project, wid)["graph"],
  runs, locate=True)`. `closed` = klíče nálezů mainu, které ve worktree nejsou; `opened` = nálezy worktree,
  které na mainu nejsou (nejvýš 50 na worktree, v pořadí kontroly). Worktree bez rozdílu se vypisuje taky
  (prázdné `closed`/`opened`).
- **Klíč nálezu** = `rule|nodeId|edgeId|journeyId|solverId|message` (chybějící část prázdná), funkce
  `map_check.finding_key`. Stejný klíč používá dávka plánu (§5.3 `docs/architektura-pro-agenty.md`, identita tam
  nese i místo řešení `place` = `solverId`; hrana může změnit zdroj). Nálezy obou stran jsou s `locate=True`.
- `journey.unverified` se z klíčů mainu pro `closed` vynechává; worktree, jehož pohled nejde přečíst (chybí
  složka, Git selže), se ve výpisu vynechá.
- `journey.unverified` se ve worktree nehodnotí (doklady cest jsou projektové, `runs=None` pro worktree), takže
  ho worktree nikdy „nezavře“ ani neotevře.
- Cache v paměti procesu podle `(project, wid, digest pohledu)`; nečinný worktree nic nestojí. Projekt bez
  Gitu (`draft`) má `worktrees: []`.
- Nic se nezapisuje, žádná tabulka ani změna schématu, žádné LLM.

## 4. Kdo co čte

| Čtenář | Co dostane |
|---|---|
| `GET /api/project-architecture/map-check/worktrees?project=` | celý `worktree_overlay` |
| agent-state (prostor `w`) `mapGaps` | díry mainu; díra zavřená ve `w` **chybí** (agent ji zalepil); díra zavřená v jiném worktree nese `inProgress: {workspaceId, branch, actor}` a agent ji nebere; nové díry z `w.opened` přibudou s `origin: "worktree"` na začátek fronty (agent je způsobil, opraví je první). `mapGapsTotal` počítá výsledek. |
| agent-state na `main` / `draft` | díry mainu, zavřené ve worktree s `inProgress` |
| node-brief karty v prostoru `w` (`holes`) | díry karty spočtené nad pohledem `w` (tatáž funkce `check_map`) |
| strážce `mapa`, trend | beze změny, jen main |

## 5. Co uvidí člověk

- **Studio (Skutečnost) a Mapa domény:** karta, na které nebo pod kterou se pracuje ve worktree (zavírá nebo
  otevírá díru, nebo nese lease / kartu v práci z `work-status`), má **jinou barvu i tvar**: vlastní token
  `--studio-worktree`, dvojitý čárkovaný rám se seříznutým rohem a ikona větve se jménem větve. Rodič ve
  fraktálu to sčítá („2 worktree“). Odznak díry rozliší „3 díry · 1 v práci“.
- **Velín – panel „Práce ve worktree“:** pro každý worktree řádek větev · aktér · „zavírá N děr · otevírá M nových“;
  rozbalení vypíše nové díry s klikem na kartu. Nové díry jsou jantarové: je to místo, kde člověk kontroluje
  práci po cestě a může změnit směr.
- `prefers-reduced-motion` a barvoslepost: stav nese i tvar a text, ne jen barva.

## 6. Rozhodnutí uživatele (2026-10-28)

1. Musí to být vidět, hlavně worktree: jiná barva i tvar karty, aby bylo vidět, že agenti na tom stromě pracují.
2. Musí v tom být přehled: budoucí díry mohou ovlivnit rozhodnutí, práci je potřeba kontrolovat po cestě.
3. Pro správné odpovědi agentům: samostatná logika (§3), jeden zdroj pro všechny čtenáře.

## 7. Etapy

| PR | Obsah |
|---|---|
| W1 | backend: `map_check_worktrees.py` + test, route, agent-state `mapGaps`, brief `holes` nad pohledem prostoru, skill |
| W2 | frontend: Studio a Mapa domény (barva, tvar, agregace), velín „Práce ve worktree“ |
