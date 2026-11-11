# Layout | Design (vrstva 1)

Přepínač pohledu vrstvy **1 Layout** a pruh **Design webu** (`docs/navrhy/2026-11-10-platno-2.md`, Verze 6).

- `components/DesignStrip.tsx`: `LookSwitch` (Layout | Design, změnu hlásí rodiči) a pruh Design webu nad mřížkou: barevné vzorky, písma (`Aa` v písmu rodiny), ukázka tlačítka a odkaz **Správa webu →** (jen když rodič dá `onOpenSite`). Dílek nic nečte ani neukládá; tokeny dostane hotové.
- `logic/design-look.ts` (test vedle): `lookOf` / `withLookParam` (adresa `look=design`, výchozí Layout bez parametru), `designSwatches` (barvy v prvním tématu, aliasy rozbalené), `designFonts`, `designButton`.
- `logic/use-look.ts`: pohled v adrese (přežije obnovení a návrat z plátna logiky; `App` parametr `look` zachovává jako `boxId`).
- `logic/use-design-tokens.ts`: tokeny Design systému projektu z dokumentu Správy webu (`GET /api/site-admin?project=`, `design.tokens`); chyba = `null`. Kontrakt jmenuje `GET /api/design-system`, ten v backendu není (jen `/api/oporahub/design-system` s DESIGN.md), proto se čte zdroj pravdy tokenů Správy webu. Stejná data dostane panel skenu pro změny tokenů staré → nové.
- `styles/design-look.css`, předpona `design-look`.

Pohled Design kreslí `../design-page/` (přes `layout-canvas/` s `look="design"`): stránka v celku, výřezy boxů celé pod sebou, jinak popis vzhledu `look`.
