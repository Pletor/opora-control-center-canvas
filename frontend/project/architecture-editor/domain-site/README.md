# Web domény (sdílená logika a formuláře)

Dříve Mapa domény. Obrazovka zanikla (strukturu stránek teď mění Struktura na plátně 2, `page-editor/project-tree/`, kontrakt `docs/navrhy/2026-11-10-platno-2.md`); zůstalo to, co čte přehled domén, plátno 2, Studio, Velín a Detail prvku.

- `components/ArchitectureProductForm.tsx` je formulář domény (přehled domén `landing/`) a stránky (Struktura na plátně 2: + Stránka, + Podstránka, přejmenování). Pole stránky skládá `PageIntentFields.tsx`: cesta, **Cíl stránky** (`goal`), **Působení** (`feel`), **Popisek v menu** (`navLabel`) a sekce ve sdíleném dílku `page-sections/` (`PageSectionsEditor`); každá změna zachová zbytek `site`. U existující stránky nabídne vstup na plátno záměru (`intent`).
- `logic/page-site.ts` (test vedle): `pageSiteForSave` (normalizuje cestu, ořízne text, prázdná pole vynechá, nic nedoplní), `withPageIntent`, `addSection` / `updateSection` / `removeSection` / `moveSection`, `navLabelOf`, popisky rolí sekcí. Kontrakt `docs/architektura-pro-agenty.md` §3.1.
- `logic/site-platform.ts` (test vedle): platforma domény, adresa (host nebo bundle ID) a `applicationSiteForSave` pro formulář domény.
- Cesty zákazníka (`site.journeys` domény, `docs/cesta-zakaznika-a-brief.md`) se tu jen čtou: `logic/journeys.ts` (kroky, odbočky, validace, signál kroku), `logic/journey-via.ts` (akce přechodu a věta signálu), `logic/derived-journeys.ts` (odvozené přechody a `lastRun` z `GET /api/project-architecture/journeys`, čte je Studio a stav karet), `logic/journey-verification.ts` (odznak ověření cesty), `logic/page-journeys.ts` (na kterých cestách stránka leží, záložka Stránka v Detailu prvku). Každý soubor má test vedle.
- `map-check/` – kontrola mapy (díry, `GET /api/project-architecture/map-check`): panel `MapCheckPanel` ukazuje plátno 2 pod **Zkontrolovat plán** jen pro otevřenou stránku; kontrolu přes worktree čte i Studio a Velín.
- `styles/domain-site.css`, předpona `domain-site`.
