# Noční směna 2026-10-14/15 (relace B): karty pro agenty, proces na kartě, mapa, velké plátno

Zadání člověka: posunout design plátna. Karty specializované pro agenty mají být pro člověka čisté a přehledné
(infografika, mnemotechnika, booleovské přepínače), na kartě mají přibýt kuličky procesu (security, kritik),
má být jasné, kam se data ukládají a jak se předávají, velké plátno nesmí padat, mapa projektu má dávat smysl
nebo se vyměnit, a má vzniknout postup, jak tvořit detail karet a řídit vývoj z terminálu i z Opory.

Souběžně běží relace A (Schránka řízená agenty, `docs/navrhy/2026-10-15-nocni-smena.md`). Tahle relace
**nesahá** na: `brief-vault*` (frontend i backend), `brief_vault_mirror`, `integrations/mirror_client`,
`tools/opora.py`, `docs/asistent.md`, `docs/schranka-*`, `CLAUDE.md`, `canvas_versions`, `database/schema`,
`.claude/skills/opora-control-center/scripts/opora_cycle.py`.

Claude Design (MCP) je nedostupný (HTTP 403), design se dělá přes existující tokeny a zásady `frontend-design`.

## Co je hotové před směnou (zjištěno)

- Pipeline karty (etapy work / test / review / fix / critic s pohledy user / sly / hacker, profil security…)
  existuje v datech (`state.nodes[id].stages`) a v bloku vedle karty (port „pipeline“). **Na kartě samotné
  není vidět.** Frontier v UI nese jen status, ne `pipeline`.
- Kontrolní pás (10 polí) a vazby s obálkou předávky už na kartě jsou.
- Výkon: opravy 1–4, 6–8 z `2026-10-14-vykon-platna.md` jsou v mainu. Zbývá 5 (jen viditelné karty: drafty),
  9 (klid v App), 10 (MiniMap, hrany, animace) a varování u stropu 2000 uzlů.
- Mapa projektu = Graphify `graph.html` (vis-network, 1780 uzlů, 109 komunit pojmenovaných „Community N“)
  v iframe. Pro člověka nečitelná a těžká; Archify HTML 700 kB vedle ní.
- Paměť rolí (OpenViking) má kontrakt a backend (`docs/pamet-agentu.md`), v node-brief je `roleMemory`.

## Kusy

| Kus | Obsah | Soubory | Stav |
|---|---|---|---|
| D1 | **Proces na kartě**: řada kuliček etap pipeline (druh = barva, kritik podle pohledu, security = hacker, stav = výplň, aktuální = kroužek, uvíznutí = jantar), čip profilu, „čeká na router“ u nenasměrované karty; v oddálení jen tečky | `node-card/logic/card-process.ts` (+test), `node-card/components/CardProcess.tsx`, `layer-nodes.ts` (pole `process`), `NodeCard.tsx`, `node-card.css` | |
| R1 | **Mazání nepoužívaného** (měření na živých datech: fáze 195/208 discover, kritéria 13, kroky 3, akce 4, scénář/fakta/design/stahování 0): panel Postup-kritéria-kroky, čip fáze, scénář, fakta, design, přepínač stahování, procesy v detailu | frontend | běží |
| V1 | **Velín** místo módu Mapa (Archify iframe): pyramida oblast → sektor → karta, pruhy stavů, kuličky, fronta „Čeká na tebe“ | `frontend/editor/control-tower/`, `App.tsx` | běží |
| A1 | **Záměr oblasti**: záměr na rámečku a v inspektoru první, souhrn sektorů, „Rozložit na sektory“ (zadání pro agenta), recept `references/rozklad.md` | `area/`, skill reference | běží |
| D2 | **Čistá karta**: inline styly pryč, jednotné řádky `node-card__row`, mnemotechnické ikony místo emoji mixu, booleovský přepínač jako switch, frontier / sektor / lease / kontroly jako infografika | `node-card/components/*` (CardFrontier, SectorProgress, CardChecks, WorkNow, CardLease, CardUsage, InputSecurity), `node-card.css` | po D1 |
| P1 | **Velké plátno nepadá**: drafty bloků v úložišti (klíč nodeId+blockId+základ), `CULL_VISIBLE` zapnuto, MiniMap jen do 500 uzlů, varování u 80 % stropu 2000 uzlů, hrany `straight` nad 1000 | `node-card/logic/block-drafts.ts` (+test), `CardBlocks.tsx`, `layer-nodes.ts` (konstanty), `Board.tsx`, `board-bar.css` | |
| M1 | **Mapa projektu**: serverový přehled Graphify (komunity pojmenované podle společné cesty, velikost, vazby mezi komunitami, hlavní soubory) + vlastní lehká SVG mapa v Projektu; původní HTML jen na vyžádání | `backend/project/maps/graphify_overview.py` (+test), `graphify_routes.py` (`GET /api/graphify/overview`), `frontend/project/maps/project-map/*`, `GraphifyMap.tsx` | |
| T1 | **Postup a úložiště**: `docs/rizeni-vyvoje-z-karty.md` — kde které datum karty žije a kudy teče (graf, stav, prostor agenta, zprávy na vazbách, kola, paměť role), jak tvořit detail karty, kdy řídit z terminálu a kdy z Opory, co znamenají kuličky procesu | `docs/` | po D1, M1 |
| K | Kritici: ChatGPT (`codex exec --sandbox read-only -`, diff v promptu) a Hermes (`hermes -z`) k D1, P1, M1 | | průběžně |

## Pravidla směny

Kontrakt → subagent s přesným zadáním → kritik → ověření hlavním vláknem (`uv run pytest backend`, `npm test`,
`npm run build`) → commit na `main` po kusech. Nic se nepushuje. Živá data se nemění. Soubory relace A se nečtou
ani neupravují; commit obsahuje jen soubory této relace (`git add` po cestách, nikdy `-A`).

## Průběh

| Čas | Krok | Stav |
|---|---|---|
| 23:10 | průzkum: kontrakt karty, výkon, mapy, pipeline, rozsah relace A | hotovo |
| 23:40 | D1 kuličky procesu, P1 drafty + kreslení jen viditelných, kritik ChatGPT 6 nálezů → opraveno (c42a92f) | hotovo |
| 23:55 | zadání člověka: pyramida, velín, mazat nepoužívané → měření na živých datech, `docs/pyramida.md` | hotovo |
| 00:05 | M1 přehled komunit + lehká mapa (b3480c1); Hermes kritik k `rizeni-vyvoje-z-karty.md` 10 nálezů → §7 | hotovo |
| 00:30 | R1 mazání (panel Postup/kritéria/kroky, fáze, scénář, fakta, design, stahování, procesy) + sirotci ProjectMemoryPanel a AgentPacketPanel (sloty v3 bez montáže) | hotovo, čeká na commit |
| 00:35 | V1 Velín v módu Mapa; kritik ChatGPT 6 nálezů (hloubka, chybějící work overview, O(A·R·N), fronta nad 50, klíč oblasti, popisky) → opravy | hotovo |
| 00:40 | A1 záměr oblasti na rámečku + inspektor + „Rozložit na sektory“ + `references/rozklad.md` (odkaz v SKILL.md, test skill docs 5/5); kritik Hermes 8 nálezů → opraveno; commit 7465a5a | hotovo |
| 01:20 | S1 sektor → karty (rozklad, ukázky ověřené proti backendu), D2 karta bez inline stylů (řádky 6/13, čipy, pruhy) | hotovo |
| 02:30 | B1 štíhlý node-brief: bez `criteria`, `steps`, `phase`, brána fáze smazána; kontrakt `karta-pro-agenty.md` upraven; backend 2077 zelených (2 známé pády graphify), FE 1165, build OK | hotovo |
| 03:00 | Z1 „Předat agentovi“ na kartě, „Shrnout podněty“ na sektoru; T2 potvrzení z fronty velína (dvojí klik, za sektor) | hotovo |
| 03:40 | ověření v headless Chrome (karty, oblasti, Velín nad Ample 143 karet); opravy: karta bez pipeline „čeká na router“ (593a8ad), kontejnerové karty a oblasti ve vrstvách (09d763e), záměr oblasti dole (033db01), průchozí řetěz + bezpečné potvrzení + zadání s daty odděleně (0a4df39) | hotovo |
| 03:50 | V4: rozvržení Velínu, fronta hlídá záměry oblastí a podstatu sektorů, zadání pro router (ce530ca); snímek: Ample 143 karet, 23 položek fronty (5 ke schválení, 18 záměrů) | hotovo |

## Ráno (co zbývá člověku)

1. Backend už běží s novou route mapy (restartovala relace A). Paměť rolí: klíč OpenVikingu je v `.env`; po dalším
   restartu `POST /api/memory/provision {"confirmed": true}` (Nastavení → paměť, nebo curl) a `GET /api/memory/status`.
2. Prohlédnout v prohlížeči: Velín a plátno jsou ověřené headless snímky (scratchpad relace B); neověřené zůstává:
   inspektor (Předat agentovi, Rozložit, Shrnout podněty), kopírování do schránky, mapa kódu v Projektu.
3. Vyzkoušet pyramidu na Ample: napsat záměr jedné oblasti → zkopírovat zadání → `claude` v kořeni Ample → dávku
   potvrdit jedním rozhodnutím.
4. Nestaví se zatím: `previousRounds[].criteria`
   a `depends_on[].status` v balíčku (stará data).
