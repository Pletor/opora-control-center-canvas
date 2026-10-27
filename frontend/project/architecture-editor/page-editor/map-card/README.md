# Karta Mapy architektury

Uzel React Flow pro Editor stránky v designu karet Studia (TechViz). Karta dostává hotová data (`cardSummary`, `areaSectorLabel` z `../logic/canvas-model.ts`, stav z `../../card-state/`, porty z `logic/card-face.ts`) a stabilní `actions`, které plátno směruje na aktuální callbacky rodiče. Nic neukládá.

- `components/ArchitectureCard.tsx` – sektor / uzel / podstránka: tmavá deska 8 px se stínem, hlavička (ikona Lucide v barvě vrstvy, název, štítek stavu plán / staví se / hotovo / ověřeno / díra, menu ⋮ Otevřít detail / Otevřít v Editoru), druh s adresou (cesta podstránky, `card.tech`), účel, buňky potomků (`CardStages.tsx`, až tři, klik vybere, dvojklik otevře detail, „+ N dalších“) a pata se souhrnem („3 uzly · 2/3 stojí“), odznakem děr a akcemi „+ Komponenta“, „Detail ↗“. Rám nese barvu stavu, „staví se“ dýchá (`card-state__frame--building`). Podstránka (`summary.page`) má čárkovaný rám a jedinou akci „Otevřít stránku →“; porty zůstávají kvůli navigačním vazbám. Komentář je tlumená poznámka bez portů.
- `components/AreaFrame.tsx` – oblast jako skupina Studia: průsvitný čárkovaný rám 18 px, popisek velkými písmeny 10 px, počet sektorů, „+ Sektor“, tahadla rozměru (`NodeResizer`, 120–20 000 px, `actions.resizeArea`).
- `logic/card-face.ts` (test vedle) – druh a podtitulek karty, barva portů podle převládajícího `carries` vazeb vstupu / výstupu (`dominantFlow` ze Studia); volný port = prázdný kroužek.
- `styles/map-card.css`, blok `map-card`.

Porty: úchyty jsou `PortHandle` ze `shared/flow-ports` (oblast = `flow`, uzel / sektor = `next`), zásah 26 px a bod 10 px stálé při zoomu (`PortZoomVar`); barvu dodává `map-card__port--<carries|open>` přes `--port-fill` / `--port-ring`. Výstupní port uzlu / sektoru: klik (pod prahem pohybu) nebo Enter volá `actions.openPortMenu` – nabídka vazby (`port-menu/`); tah dál táhne vazbu. Karta kroku nově ověřené cesty dostane na uzel jednorázový pulz `studio-motion__pulse` (`map-link/`).
