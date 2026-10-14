# Živý stav domén (web a worktree)

Provádí `docs/domeny-a-worktree.md` §10 (F2): u každé domény je vidět, jestli web běží a kdo na ní pracuje. Na přehledu domén (`landing/`) žeton webu, věta s počty („3 worktree · 1 běží · 1 čeká“) a sbalitelný stěsnaný strom worktree; v detailu domény (`domain-map/`) pravý panel s webem hostu, stromem worktree a akcemi vybraného worktree.

Dílky (`components/`) dostávají hotová data v props a nic nenačítají:

- `WebStatusBadge`: žeton webu (ikona + slovo + latence, podrobnosti v `title`). Chybějící DNS je neutrální. Stejný žeton je v hlavičce plátna stránky (`PageEditor`) a v levém panelu domény u projektu bez worktree.
- `LiveWebSection`: horní část panelu, žeton a „Ověřit znovu“ (zakázané 30 s po poslední kontrole hostu, `title` „Další ověření za 18 s“, odpočet `logic/use-refresh-wait.ts`).
- `SessionChip`: jedna relace. Hlavní slovo je **stav worktree spočítaný backendem**, ne surový stav zdroje (hook `active` po 120 s ticha ani převzatá karta bez aktivity nesmí vypadat jako „běží“ / „čeká“); surový stav a „naposledy před 4 min“ jsou v `title`. Čip relace asistenta otevře tu relaci (`onOpenSession`).
- `WorktreeTree` + `WorktreeRow`: strom `role="tree"`, nejživější nahoře, roving tabindex (jedna zastávka Tab, šipky nahoru/dolů, vpravo/vlevo rozbalí/sbalí, Home/End, Enter/mezera použije). Pod worktree jsou relace a karty v práci; název karty otevře kartu v jejím worktree (`onOpenCard({workspace, nodeId})`). Klik na worktree ho jen vybere a zvýrazní dotčené stránky.
- `WorktreeDetails`: akce vybraného worktree pod stromem: „Pracovat v tomto worktree“, „Nová relace“, „Nová relace pro kartu“.
- `LiveDomainPanel`: pravý sloupec mapy domény (jen schopnost `worktreeLive`); prázdný stav „Na této doméně se teď nepracuje.“ + „Nový worktree“; zastaralá data „údaj z 12:03, nepodařilo se obnovit“; `aria-live` hlásí jen změny stavu.

Logika (`logic/`), čisté funkce s testem vedle:

- `live-model.ts`: tvar a normalizace stavu práce (včetně `mainSessions`), řazení, věta s počty, stránky dotčené worktree (`pagesTouched`, `pageWorkCounts` pro odznak na `PageCard`).
- `web-status.ts`: tvar stavu webu, slova a tóny, `applyHosts` (plná odpověď nahradí celý seznam, odpověď domény všechny hosty té domény), odpočet ručního ověření, zastaralost podle `checkedAt`.
- `web-slots.ts`: web po doménách: načítání, chyba a čas zvlášť pro celý projekt (`*`) a pro každou doménu; `webView` vybere novější událost.
- `session-state.ts`: slova a ikony stavů, čip relace podle stavu worktree, souhrn hlavních relací („nenačteno“ ≠ „žádná“), věta pro `aria-live`, název nové relace, `CardRequest`.
- `tree-nav.ts`: klávesnice stromu (viditelné položky, zastávka Tab, pohyb).
- `live-poll.ts`: intervaly (10 s detail, 30 s přehled, web 60 s), odstup po chybě 10 → 20 → 60 s, paměť posledních dat, věta o selhání prvního čtení.

Data načítá jen `../logic/use-domain-live.ts` přes sdílený `usePolling` (odpovědi předběhnutých dotazů se zahodí i při chybě); drží je `ArchitectureEditor` a převádí přes `../logic/live-views.ts`. Akce jdou nahoru do `App`: přepnutí worktree (stejný kód jako výběr v TopBaru), nová relace (otevře panel Asistent a založí úkol bez zprávy), otevření relace (panel Asistent ji vybere), otevření karty (přepne prostor, je-li jiný, a kartu vybere v Editoru), nový worktree (modal s výběrem domény). Lokální projekt (schopnost `worktreeLive = false`) strom ani panel nevykreslí, web ano.

Styl `styles/live-status.css`, blok `live-status`; tvar žetonů převzatý z `agent-summary__work`.
