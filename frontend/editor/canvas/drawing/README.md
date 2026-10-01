Kreslicí nástroje a stav kresby na plátně (DrawingTools, DrawingWorkspace).

- `components/DrawingWorkspace.tsx` skládá Excalidraw, stav uložení a postranní wireframe panel.
- `components/wireframe-elements.ts` vytváří prvky wireframu vložené do kresby a jejich podobu pro inspektor.
- `components/use-drawing-files.ts` načítá obrázky k otevřené scéně a nahrává je před uložením scény.
- `logic/drawing-state.ts` drží drafty, rozpracovaná uložení, mezipaměť obrázků a seznam nástrojů.
- `logic/drawing-files.ts` (+ test) říká bez Reactu, které obrázky scéna potřebuje, co nahrát a co se smí vložit.

Obrázky: screenshot přes Ctrl+V, přetažení souboru nebo nástroj Obrázek. Povolené jsou PNG, JPEG, WebP a GIF do 10 MB.
Scéna nese jen `fileId`; data obrázku se ukládají zvlášť (`POST /api/drawing-file`, `GET /api/drawing-files`) jednou
na projekt. Uložení kresby nejprve nahraje chybějící obrázky; server scénu s nenahraným `fileId` odmítne a místní draft
zůstane. Obrázek z URL, webové vložky (embed, iframe) a import jiných souborů zůstávají zablokované.
