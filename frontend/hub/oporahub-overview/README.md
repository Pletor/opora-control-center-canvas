# Rám OporaHubu

`OporaHubOverview` je rám prostředí: hlavička se záložkami (Přehled · Karta · Pro agenty), jeden dokument agent-state, jeho zrcadlo `<script type="application/json" id="oh-agent-state">` a pata `LegacyLinks`, která otevírá všechny původní drawery a formuláře. Návrh: Claude Design „OporaHub — přehled“ (`01-prehled`, `02-karta`, `03-agenti`).

`OverviewDrawer` má ✕ vpravo nahoře, Escape, focus trap, inertní pozadí a návrat focusu; varianta `wide` slouží detailu karty. `ExactDetail` a `FocusedDetail` drží přesný vybraný záznam ve starších detailech. `logic/overview.ts` zůstává pro starší detaily (přijatá hlava pro formální podklady). Pravidla rozhraní: `docs/oporahub-ui.md`.
