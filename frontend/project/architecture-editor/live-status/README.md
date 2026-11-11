# Živý stav domén (web a worktree)

Provádí `docs/domeny-a-worktree.md` §10 (F2): u každé domény je vidět, jestli web běží a kdo na ní pracuje. Na přehledu domén (`landing/`) žeton webu, věta s počty („3 worktree · 1 běží · 1 čeká“) a sbalitelný stěsnaný strom worktree; na plátně 2 žeton webu hostu v hlavičce stránky. Pravý panel s webem hostu, stromem worktree a akcemi (`LiveDomainPanel`) po zániku Mapy domény zatím nikde není.

Dílky (`components/`) dostávají hotová data v props a nic nenačítají:

- `WebStatusBadge`: žeton webu (ikona + slovo + latence, podrobnosti v `title`). Chybějící DNS je neutrální. Stejný žeton je v hlavičce plátna stránky (`PageEditor`) a v levém panelu domény u projektu bez worktree.
- `LiveWebSection`: horní část panelu, žeton a „Ověřit znovu“ (zakázané 30 s po poslední kontrole hostu, `title` „Další ověření za 18 s“, odpočet `logic/use-refresh-wait.ts`).
- `SessionChip`: jedna relace. Hlavní slovo je **stav worktree spočítaný backendem**, ne surový stav zdroje (převzatá karta bez aktivity nesmí vypadat jako „běží“ / „čeká“); surový stav a „naposledy před 4 min“ jsou v `title`. Zdrojem je lease karty.
- `WorktreeTree` + `WorktreeRow`: strom `role="tree"`, nejživější nahoře, řádek nese aktéra a krátké ID (nikdy celou větev), roving tabindex (jedna zastávka Tab, šipky nahoru/dolů, vpravo/vlevo rozbalí/sbalí, Home/End, Enter/mezera použije). Pod worktree jsou relace a karty v práci; název karty otevře kartu v jejím worktree (`onOpenCard({workspace, nodeId})`). Klik na worktree ho jen vybere a zvýrazní dotčené stránky.
- `WorktreeDetails`: akce vybraného worktree pod stromem: „Pracovat v tomto worktree“, „Zadat srdci“ (worktree i jednotlivá karta; text jde přes `onAskHeart` do App, která ho pošle `POST /api/brain/heart/messages` a otevře panel asistenta) a na konci „Do skladiště…“ (nejde u worktree, ve kterém právě pracujete).
- `ArchiveConfirm`: potvrzení přesunu do skladiště s povinným důvodem („nápad nevyšel“); odmítnutí backendu (změny, živá relace) ukáže pod polem.
- `LiveDomainPanel`: dříve pravý sloupec Mapy domény, po plátně 2 (`docs/navrhy/2026-11-10-platno-2.md`) zatím nikde složený (jen schopnost `worktreeLive`); prázdný stav „Na této doméně se teď nepracuje.“ + „Nový worktree“; zastaralá data „údaj z 12:03, nepodařilo se obnovit“; `aria-live` hlásí jen změny stavu.

Logika (`logic/`), čisté funkce s testem vedle:

- `live-model.ts`: tvar a normalizace stavu práce řazení, věta s počty, stránky dotčené worktree (`pagesTouched`, `pageWorkCounts` pro odznak na `PageCard`).
- `web-status.ts`: tvar stavu webu, slova a tóny, `applyHosts` (plná odpověď nahradí celý seznam, odpověď domény všechny hosty té domény), odpočet ručního ověření, zastaralost podle `checkedAt`.
- `web-slots.ts`: web po doménách: načítání, chyba a čas zvlášť pro celý projekt (`*`) a pro každou doménu; `webView` vybere novější událost.
- `session-state.ts`: slova a ikony stavů, čip relace podle stavu worktree, věta pro `aria-live`, text pro srdce (`heartText`), `CardRequest`.
- `worktree-label.ts`: jméno worktree na obrazovce: aktér + krátké ID (8 znaků), větev a plné ID jen v `title`; `worktreeName` pro věty a názvy relací („01-start-projektu · a0f1764b“).
- `tree-nav.ts`: klávesnice stromu (viditelné položky, zastávka Tab, pohyb).
- `worktree-archive.ts`: tvar skladiště, kontrola důvodu, datum, proč přesun nejde.
- `live-poll.ts`: intervaly (10 s detail, 30 s přehled, web 60 s), odstup po chybě 10 → 20 → 60 s, paměť posledních dat, věta o selhání prvního čtení.

Data načítá jen `../logic/use-domain-live.ts` přes sdílený `usePolling` (odpovědi předběhnutých dotazů se zahodí i při chybě); drží je `ArchitectureEditor` a převádí přes `../logic/live-views.ts`. Akce jdou nahoru do `App`: přepnutí worktree (stejný kód jako výběr v TopBaru), nová relace (otevře panel Asistent a založí úkol bez zprávy), otevření relace (panel Asistent ji vybere), otevření karty (přepne prostor, je-li jiný, a kartu vybere v Editoru), nový worktree (modal s výběrem domény). Lokální projekt (schopnost `worktreeLive = false`) strom ani panel nevykreslí, web ano.

Styl `styles/live-status.css`, blok `live-status`; tvar žetonů převzatý z `agent-summary__work`.
