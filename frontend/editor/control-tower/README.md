# control-tower (Velín)

Velín zobrazuje projekt → vrstvu → sektor → kartu jako pilulky seřazené podle `topoIndex`, rozhodnutí pro
člověka, další připravené akce a „Teď běží“ s odpočtem pronájmu. Stav bere výhradně ze sdíleného čtení
`GET /api/oporahub/agent-state` (`cards[]`, `decisions[]`, `actions[]`; `hub/oporahub-agent-state`), z grafu
plátna jen jména a příslušnost k sektoru. Model `logic/velin-model.ts` (test `velin-model.test.ts`), dílky
`components/` (rám a filtry, vrstva, pravý sloupec, Teď běží), styl `styles/velin.css`. Nic nezapisuje:
klik otevře detail karty přes `frontend/hub/oporahub-card-drawer/open.ts`. Zrcadlo pro agenty `script#oh-velin`.

Strážci (`docs/strazci.md` §5): řádek „Strážci ✓ / ⚠ N“ z `GET /api/strazci?project=` (poslední běh, chyba strážce;
`logic/use-guard-status.ts`, 30 s) a otevřené nálezy z agent-state `guards.findings` (klik → karta), logika
`logic/velin-guards.ts` (test `velin-guards.test.ts`), dílek `components/VelinGuards.tsx`. Strážce `mapa` se nepočítá,
díry mapy má řádek „Díry mapy“. Panel Trend: osm malých křivek za 14 dní z `GET /api/strazci/trend?project=&days=14`
(`logic/use-guard-trend.ts`, 5 min), logika `logic/velin-trend.ts` (test `velin-trend.test.ts`), dílek
`components/VelinTrend.tsx`. Pilulky „na tebe“, rozhodnutí a záložka filtru „Na tebe“ (když čeká aspoň jedno, `velin__filter--waiting`) dýchají čárkovaným zlatým rámem
(`docs/zive-zobrazeni-a-knihovna.md` §3, bez pohybu při `prefers-reduced-motion`).

Práce ve worktree (`docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md` §5): panel pod strážci, řádek na worktree
„větev · aktér · zavírá N děr · otevírá M nových“, rozbalení (`<details>`) vypíše nové díry jantarově se značkou „＋“
a klik na díru s kartou ji otevře (`onOpen`, jako strážci). Zdroj `GET /api/project-architecture/map-check/worktrees`
přes sdílený `project/architecture-editor/logic/use-map-worktrees.ts` (30 s, jen se schopností `worktreeLive` od App),
logika `logic/velin-worktrees.ts` (test `velin-worktrees.test.ts`), dílek `components/VelinWorktrees.tsx`. Bez worktree nic.
