# Přehled OporaHubu

Jedna výchozí stránka skládá přijatý plán, rozhodnutí, práci agentů, další kroky a doloženou aktivitu. Vychází z Claude Code návrhu v `docs/design/oporahub-overview.html`; ukázkové názvy, počty ani revize nepřebírá.

Rodič vlastní všechny existující hooky a mutace. Přehled pouze promítá dodaná data a otevírá konkrétní návrh, execution nebo důkaz v cíleném detailu. Drawer má ✕, Escape, focus trap, inertní pozadí a návrat focusu. Změna scope detail zavře. Zavření ruší rozepsaná potvrzení limitů a cancellation.

Počty popisují načtené historie s limitem 100; nikdy globální počet úloh. Nahrazené grafové návrhy se nepočítají znovu. Jiný rodič je zastaralý. Nedostupné podklady a rozporné přijaté hlavy zůstávají viditelné. Aktivní stav běhu se lokálně zneplatní po uplynutí načteného oprávnění; reported, review, pozorovaný merge a nasazení jsou oddělené pojmy.

Čisté projekce a jejich hranice ověřuje `logic/overview.test.ts`. Pravidla rozhraní jsou v `docs/oporahub-overview.md`.
