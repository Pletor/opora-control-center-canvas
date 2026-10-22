# control-tower (Velín)

Velín zobrazuje projekt → vrstvu → sektor → kartu jako pilulky seřazené podle `topoIndex`, rozhodnutí pro
člověka, další připravené akce a „Teď běží“ s odpočtem pronájmu. Stav bere výhradně ze sdíleného čtení
`GET /api/oporahub/agent-state` (`cards[]`, `decisions[]`, `actions[]`; `hub/oporahub-agent-state`), z grafu
plátna jen jména a příslušnost k sektoru. Model `logic/velin-model.ts` (test `velin-model.test.ts`), dílky
`components/` (rám a filtry, vrstva, pravý sloupec, Teď běží), styl `styles/velin.css`. Nic nezapisuje:
klik otevře detail karty přes `hub/oporahub-card-drawer/logic/open.ts`. Zrcadlo pro agenty `script#oh-velin`.
