# Živý stav domén (web a worktree)

Provádí `docs/domeny-a-worktree.md` §10 (F2): u každé domény je vidět, jestli web běží a kdo na ní pracuje. Na přehledu domén (`landing/`) žeton webu, věta s počty („3 worktree · 1 běží · 1 čeká“) a sbalitelný strom worktree jen ke čtení; v detailu domény (`domain-map/`) pravý panel s webem hostu, stromem worktree a akcemi.

Dílky (`components/`) dostávají hotová data v props a nic nenačítají:

- `WebStatusBadge`: žeton webu (ikona + slovo + latence, podrobnosti v `title`). Chybějící DNS je neutrální.
- `SessionChip`: jedna relace (asistent, hook, převzatá karta) se stavem slovem.
- `WorktreeTree` + `WorktreeRow`: strom `role="tree"`, nejživější nahoře; rozbalený worktree ukáže relace, karty v práci a (jen v panelu) „Pracovat v tomto worktree“, „Nová relace“ a u karty „Nová relace pro kartu“. Klik na worktree ho jen vybere a zvýrazní dotčené stránky.
- `LiveDomainPanel`: pravý sloupec mapy domény; prázdný stav „Na této doméně se teď nepracuje.“ + „Nový worktree“; zastaralá data s „údaj z 12:03“; `aria-live` hlásí jen změny stavu.

Logika (`logic/`), čisté funkce s testem vedle:

- `live-model.ts`: tvar a normalizace stavu práce, řazení, věta s počty, stránky dotčené worktree (`pagesTouched`, `pageWorkCounts` pro odznak na `PageCard`).
- `web-status.ts`: tvar stavu webu, slova a tóny, sloučení výsledků podle hostu.
- `session-state.ts`: slova a ikony stavů, souhrn hlavních relací, věta pro `aria-live`, název nové relace.
- `live-poll.ts`: intervaly (10 s detail, 30 s přehled, web 60 s), odstup po chybě 10 → 20 → 60 s, paměť posledních dat.

Data načítá jen `../logic/use-domain-live.ts` přes sdílený `usePolling`; drží je `ArchitectureEditor` a převádí přes `../logic/live-views.ts`. Akce jdou nahoru do `App`: přepnutí worktree (stejný kód jako výběr v TopBaru), nová relace (otevře panel Asistent a založí úkol bez zprávy), nový worktree (modal s předvyplněnou doménou). Lokální projekt (schopnost `worktreeLive = false`) strom ani panel worktree nevykreslí, web ano.

Styl `styles/live-status.css`, blok `live-status`; tvar žetonů převzatý z `agent-summary__work`.
