# Studio

Záložka **Studio** v liště Projektu (`Architektura projektu · Studio · Graphify-out`, adresa `projectView=studio`), kontrakt `docs/studio.md`. Etapy S2–S3: vrstva **Skutečnost**, jen čtení, s pohybem toho, co se právě staví nebo právě prošlo či spadlo. Plátno v designu TechViz převzatém z vlastního prototypu `04.Architektura-projektu/prototype` (paleta, karta, porty, Bézierovy vazby, minimapa, Inspector vpravo).

- `components/Studio.tsx` – rodič. Skládá drobečky, plátno, panel detailu a na úrovni domény pás cest; drží zanoření (`studioFocus` v adrese) a výběr. Nic neukládá. „Otevřít v Editoru stránky“ hlásí nahoru (`onOpenArchitecture`), App zapíše parametry editoru (`editorId`, `domainId`, `pageId`, `architectureNode`) a přepne na Architekturu projektu.
- `logic/use-studio-data.ts` – jediné načítání: graf z `/api/view` (`useArchitectureGraph`, stejný zdroj jako Architektura projektu), uzavření karet z Desktop stavu (`done.confirmed`), stav práce z `/api/project-architecture/work-status` (`useDomainLive`, jen se schopností `worktreeLive`), díry mapy (`useMapCheck`) a cesty s `lastRun` (`use-studio-runs.ts`, sdílený poller po 15 s, protože nový doklad cesty otisk mapy nemění).
- `logic/use-studio-focus.ts` – zanoření v adrese, výběr v paměti.
- `logic/studio-tree.ts` – fraktální strom projekt → doména → stránka → sekce → komponenta (a její děti). Sekce z `site.sections` mají virtuální id `section:<stránka>:<sekce>`; komponenta stránky se sekcemi bez platné `card.section` leží na úrovni stránky ve skupině „bez sekce“. Složky, pod kterými leží stránky, se přeskakují; uzly mimo doménu Studio nekreslí.
- `logic/studio-level.ts` – `levelOf(tree, graph, focus)`: karty úrovně a souhrnné vazby (hrany `next` mezi potomky různých karet sečtené do jedné vazby, počet a převládající `carries`).
- `logic/studio-status.ts` – stav karty (plán, staví se, hotovo, ověřeno, díra) a souhrn dětí; `logic/studio-facts.ts` skládá fakta ze zdrojů.
- `logic/studio-route.ts` – `studioFocus` a parametry odkazu do Architektury projektu.
- Dílky: `studio-canvas/` (React Flow plátno), `studio-card/` (karta a rám skupiny), `studio-breadcrumbs/`, `studio-detail/` (panel vpravo), `studio-journeys/` (dráhy cest domény, přesunuté z mapy domény), `studio-motion/` (pohyb Skutečnosti: tečky stavěných vazeb, průchod nově ověřené cesty, selhání, `PresentationClock`).
- `styles/studio.css`, blok `studio`. Barvy jsou tokeny `--studio-*` v `design-tokens/styles/theme-tokens.css`, vazby `--edge-carries-*`.

Testy: `logic/*.test.ts` a v každém dílku (`npm test`).
