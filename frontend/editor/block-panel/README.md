# block-panel

Boční menu vybraného bloku = **stopa práce jeho karty** (kontrakt `docs/navrhy/2026-10-31-panel-bloku.md`,
rozhodnutí člověka 2026-10-31; návrh Claude Design „Panel bloku“, varianta 1a s relacemi a logem v jedné ose).
Nahradilo dřívější editor bloku (stav a větvení, podmínka splnění, splněno/nesplněno →, štítky, TODO,
inspirace, podbloky), který nikdo neplnil. Uložená data bloků zůstávají beze změny, jen se nekreslí.

Otevře se jen výběrem konkrétního bloku (`components/BlockPanelDrawer`, zásuvka 360 px od levé hrany plátna,
styly `node-library--wide`); zavření vrací výběr na kartu. Panel jen čte. Název a popis bloku, porty a vazby
se upravují na kartě v plátně; karta v plátně zůstává rychlý přehled a stopu práce nekreslí.

Sekce shora dolů (rodič `components/BlockPanel` skládá dílky):

1. `PanelHead`: číslo bloku, pořadí karty (`orderBadge` z card-face), ID, název, karta, popis, poslední změna karty.
2. `WorkSection`: čip stavu, etapa, segmenty a kroky ✓/…/✗/○ s kontrolou, kdo drží + „zbývá N min“, další krok,
   PR (`shared/pr-badge`), co chybí k hotovu; „teď: nástroj · soubor“ z posledního `tool.use` běžící relace.
3. `JudgmentSection`: jen s neprázdným `judgment`. Zlatá = otázka na člověka, červená = `red_twice`.
   „Odpovědět srdci“ otevře pole a odpověď (s kartou, příznakem a krokem, `heartReply`) hlásí nahoru; App ji
   pošle `POST /api/brain/heart/messages` a otevře kanál srdce. Odkaz vede do Review nebo Běhu detailu karty.
4. `TrailSection` + `TrailRunBody`: jedna osa, relace dělníků i změny karty podle času po dnech, nejvýš 10,
   rozbalená jen nejnovější relace (shrnutí, kroky, kontroly, commity, soubory). „Celá historie →“ = záložka
   Historie detailu karty (`openCardDrawer(nodeId, tab)`).
5. `PortSection`: popisek portu bloku → cílová karta, poslední zpráva na vazbě, autor a čas.

U každé položky značka původu `SourceMark` z pole `source`: ⚙ odvozeno, A dělník, ✦ srdce, H člověk.

Data a logika (`logic/`, čisté funkce s testem vedle):

- `card-trail.ts`: typy a čtení `GET /api/oporahub/card-trail` (`docs/stopa-prace-karty.md`).
- `trail-timeline.ts`: sloučená osa, dny, stavy relací, značky kroků a původu, řádka „teď“. `TRAIL_SETTINGS`
  (délka osy 10, rozbalit poslední relaci) je nastavení jednou pro aplikaci, nikdy per projekt.
- `panel-work.ts`: práce na kartě, zbývající čas, úsudek, odpověď srdci, porty.
- `panel-view.ts`: celý obsah panelu z bloku, karty z agent-state a stopy.
- `use-card-trail.ts` (bez testu): lidská UI session jako u historie běhů, jednorázové čtení, nové čtení
  s novým snímkem agent-state.

Data načítá rodič v `app/components/BlockDrawerContent.tsx`. Styl `styles/block-panel.css` (blok `block-panel`).
