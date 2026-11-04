# Rámce a poznámky plátna (`flow-frame`)

Plátno knihovny toků (kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §2) nese vedle uzlů `notes[]` a `groups[]` podle n8n: lepíky s markdownem a rámce kroků s názvem a popisem. Editor je zapne propem `frames`; srdce je nemá.

- `components/FlowNoteCard.tsx` — lepík za uzly: markdown, dvojklik = úprava textu, barva, tah a změna velikosti (`NodeResizer`). Změnu hlásí kontextem `FrameActionsContext.onNote`.
- `components/FlowGroupFrame.tsx` — rámec kolem uzlů skupiny: název, popis, sbalit/rozbalit (stav jen v prohlížeči, jako n8n), počet chyb kontroly grafu na rámci. Sbalený rámec je jedna karta s porty `in:main` / `out:main`.
- `components/GroupInspector.tsx` — panel vybraného rámce: název, popis (do 145 znaků), zrušit rámec.
- `logic/frame-actions.ts` — kontext akcí karet a barvy lepíků. `logic/note-markdown.ts` — bezpečný výřez markdownu (nadpisy, odrážky, odstavce, tučné, kód) + test.
- Čisté úpravy grafu jsou v `../logic/graph-frames.ts`, převod na uzly React Flow v `../logic/frame-view.ts` (oba s testy).
- `styles/flow-frame.css`, předpony `flow-note` a `flow-group`.
