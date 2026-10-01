Textový editor obsahu uzlu: stránka módu Text a osnova bloků.

- `TextWorkspace` skládá celou stránku (kontrakt `docs/souhrn-prace-agentu.md`). Podzáložka Uživatel
  shora dolů: hlavička (`TextWorkspaceHead`: název vrstvy, podzáložky, „rozbaleno X z Y“, Rozbalit
  vše / Sbalit vše), souhrn práce agentů (`../agent-summary/AgentSummary`), dokument vrstvy a kapitoly
  dětí (`TextChapters`). Podzáložka Agenti je `AgentSegmentsBoard` beze změny. Rodič drží jen stav
  pohledu — rozbalení a připojené editory podle vrstvy (výchozí vše sbalené), filtr, řazení, hover a
  zvýraznění po skoku ze souhrnu (1500 ms) — a nic z toho neukládá na server ani do localStorage.
  Síťový stav souhrnu je `useChapterOverviews`; nepovinný prop `refreshKey` (otisk plátna) ho obnoví.
- `TextChapters` kreslí kapitoly a rozhoduje, kdy kapitola dostane editor: až při prvním rozbalení,
  a pak zůstává připojený. `TextChapter` je jedna kapitola (`article.text-block`, modifikátory
  `--expanded`, `--highlighted`, `--hovered`): lepicí hlavička se šipkou (`aria-expanded`,
  `aria-controls`), druhem, názvem, `WorkChip` a `MemoryDots` z levného souhrnu, `CommsChips` jen
  s načteným briefem, zámkem uzavřené karty, časem změny a tlačítkem Zanořit. Sbalení tělo jen skryje
  (`hidden`), protože `NodeTextEditor` při odpojení neuloží rozepsaný text. Hover hlásí `onHover`.
- `logic/text-chapters.ts` — neměnné množiny kapitol: `toggleChapter`, `expandAll`, `collapseAll`,
  `withMounted` (sjednocení), `viewWithExpanded`, `expandedCount`.
- `NodeTextEditor` drží jeden text uzlu: načte ho, hlídá revizi, sám ukládá bloky se zpožděním
  (`AUTOSAVE_MS`) a nechává ruční uložení pro zdrojový text (zavřené `details`, Ctrl+S).
- `BlockOutline` je rodič osnovy: drží bloky, kurzor, paletu a sbalení, každou změnu posílá ven
  jedním `onChange` se serializovaným textem. `BlockRow` kreslí řádek (šipka, kulička, pole, odkazy),
  `BlockMenu` paletu po `/` a `[[`. Klávesy: Enter nový blok, Tab/Shift+Tab zanoření, Backspace na
  prázdném bloku maže, Ctrl+Enter úkol pro agenta, Esc zavírá paletu.
- `logic/block-commands.ts` je jediný model bloků (text ↔ bloky, zanoření, paleta, odkazy).
  `logic/block-tree.ts` z něj jen čte strom (děti, co skrýt při sbalení); sbalení je pohled a do
  textu uzlu se neukládá. `logic/block-view.ts` říká, jak blok vypadá (nadpis `# `, značka
  `TODO`/`DONE`/`ROZHODNUTÍ`/`DŮKAZ`, štítky odkazů).
- Styl: `styles/text-workspace.css` (stránka, hlavička a kapitoly, BEM blok `text-block`),
  `styles/block-outline.css` (osnova). `styles/node-detail-shared.css` nese starší pravidla sousedních
  dílků (deník, odkazy, oznámení) — přitahuje si ho `block-outline.css`, protože ty dílky znají jen
  jeho. Nová pravidla tam nepatří.
