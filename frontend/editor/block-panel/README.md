# block-panel

Boční menu vybraného bloku nebo karty (**panel karty**) = **stopa práce karty** (kontrakt `docs/navrhy/2026-10-31-panel-bloku.md`,
rozhodnutí člověka 2026-10-31; návrh Claude Design „Panel bloku“, varianta 1a s relacemi a logem v jedné ose).
Nahradilo dřívější editor bloku (stav a větvení, podmínka splnění, splněno/nesplněno →, štítky, TODO,
inspirace, podbloky), který nikdo neplnil. Uložená data bloků zůstávají beze změny, jen se nekreslí.

Otevře se dvěma cestami do stejné zásuvky (`components/BlockPanelDrawer`, 360 px od levé hrany plátna, styly
`node-library--wide`):

- **z bloku**: výběr konkrétního bloku v kartě (`selectBlock`, `panels.drawer === "block"`);
- **z karty**: klik na postup kroků na tváři karty (segmenty a řádka „3/7 · …“ s tichým „stopa ›“, dílek
  `editor/canvas/card-face`). Akce karty `trail` → `Board.onCardTrail` → App `selectCardTrail(id)`,
  `panels.drawer === "card"`. Karty, na kterých pracuje srdce a kancelář, bloky nemají, proto je tohle hlavní
  vstup. Pouhý výběr karty panel neotevírá.

V režimu karty hlavička ukáže „KARTA“, ID, název a účel karty místo čísla, názvu a popisu bloku; zbytek je stejný.
Zásuvka nemá vlastní lištu: zavírací × nese hlavička panelu a zásuvka leží nad lištou sektoru (`z-index` 21).
Zavření vrací výběr na kartu (pravý inspektor). Panel jen čte. Název a popis bloku, porty a vazby
se upravují na kartě v plátně; karta v plátně zůstává rychlý přehled a stopu práce nekreslí.

Sekce shora dolů (rodič `components/BlockPanel` skládá dílky):

1. `PanelHead`: v jedné řádce druh (BLOK n / KARTA), pořadí karty (`orderBadge` z card-face), krátké ID a ×;
   pod tím název, u bloku „karta …“, popis (u karty její účel), poslední změna karty „kdo · kdy · co“.
2. `WorkSection`: čip stavu a jedna věta (`line`: „etapa · krok X z Y“, „3/3 kroků“, „s2 · 2× červená“,
   „na kartu 3·02 …“ z `blockedBy`), segmenty a kroky ✓/…/✗/○ s poznámkou (kontrola jménem, bez známého výsledku
   krátký commit, u `red_twice` „2× červená“), kdo drží + „zbývá N min“ (jinak „nikdo · uvolněno HH:MM“ z
   `lease.released`), další krok, PR (`shared/pr-badge`) s počtem commitů, co chybí k hotovu; věta „Na kartě
   zatím nikdo nepracoval…“ bez relací; „teď: nástroj · soubor“ z posledního `tool.use` běžící relace.
3. `JudgmentSection`: jen s neprázdným `judgment`. Zlatá = otázka na člověka, červená = `red_twice`.
   „Odpovědět srdci“ otevře pole a odpověď (s kartou, příznakem a krokem, `heartReply`) hlásí nahoru; App ji
   pošle `POST /api/brain/heart/messages` a otevře kanál srdce. Odkaz vede do Review nebo Běhu detailu karty.
4. `TrailSection` + `TrailRunBody`: jedna osa, relace dělníků i změny karty podle času po dnech, nejvýš 10,
   rozbalená jen nejnovější relace (shrnutí, kroky, kontroly, commity, soubory). Relace: tečka stavu, kdo,
   „10:42–12:58“, „doručeno · 3 kroky“. Opakované události jednoho děje za sebou (kolo review) jsou sbalené do
   jedné řádky „společný začátek · N událostí“ s průběhem pod ní (`bundleEvents`). „Celá historie →“ = záložka
   Historie, „Všechny relace v Běhu →“ = záložka Běh detailu karty (`openCardDrawer(nodeId, tab)`).
5. `PortSection`: všechny vazby z karty (`source == karta`, v obou režimech), popisek portu bloku (bez bloku
   „vazba“) → cílová karta, poslední zpráva na vazbě (jinak „Bez zprávy na vazbě.“), autor a čas. Karta bez
   portu řekne, odkud do ní vstup přichází.

Co data stopy zatím nenesou, panel nevymýšlí: čas smyčky u příznaku, časy červených kontrol a text srdce
k příznaku (řádek ✦ má v `JudgmentView.heart` připravené místo, dnes prázdné).

U každé položky značka původu `SourceMark` z pole `source`: ⚙ odvozeno, A dělník, ✦ srdce, H člověk.

Data a logika (`logic/`, čisté funkce s testem vedle):

- `card-trail.ts`: typy a čtení `GET /api/oporahub/card-trail` (`docs/stopa-prace-karty.md`).
- `trail-timeline.ts`: sloučená osa, sbalené řady událostí, rozsah relace, dny, stavy relací, značky kroků a původu, řádka „teď“. `TRAIL_SETTINGS`
  (délka osy 10, rozbalit poslední relaci) je nastavení jednou pro aplikaci, nikdy per projekt.
- `panel-work.ts`: práce na kartě (věta vedle čipu, poznámky kroků, commity, uvolnění), zbývající čas, úsudek, odpověď srdci, porty.
- `panel-view.ts`: celý obsah panelu z bloku (nebo `block: null` = režim karty), karty z agent-state a stopy;
  `cardLabel` pojmenuje jinou kartu pořadím a názvem.
- `use-card-trail.ts` (bez testu): lidská UI session jako u historie běhů, jednorázové čtení, nové čtení
  s novým snímkem agent-state.

Data načítá rodič v `app/components/BlockDrawerContent.tsx`. Styl `styles/block-panel.css` (blok `block-panel`).
