# Audit: co v rozhraní je globální a co per projekt (2026-09-15)

Otázka: proč se dva projekty ovládají jinak a kde je jediné místo, ze kterého se chování řídí.

## Kde stav rozhraní žije

| Místo | Klíč / tabulka | Obsah | Per projekt? | Skupina |
|---|---|---|---|---|
| `frontend/app/logic/desktop-appearance.ts` | localStorage `opora:desktop-theme:v1` | barevný režim, hustota | ne, globální | A vzhled |
| `frontend/shared/surface-settings/logic/workspace-settings.ts` | localStorage `opora:surface-settings:v1` | mřížka, přichytávání, velikost mřížky, kreslicí mřížka | ne, globální | A ovládání |
| `frontend/design-tokens/styles/theme-tokens.css` | CSS proměnné | barvy, rozměry, přechody | ne, globální | A vzhled |
| `backend/claude_code/skill_preferences.py` | `claude-code-skills.json` v datovém kořeni | vypnuté skills | ne, globální | A ovládání |
| `frontend/editor/canvas/board/components/Board.tsx` | localStorage `viewport:<projekt+workspace+vrstva>` | poloha a zoom plátna | ano | B obsah |
| `frontend/shared/selection/logic/workspace-selection.ts` | sessionStorage `opora.workspace-selection.v2:<projekt,workspace>` | rozpracovaný výběr | ano | B obsah |
| `frontend/shared/hooks/logic/use-pending-edits.ts` | sessionStorage `opora.pending-edits.v1` | neuložené texty bloků | ne (klíčováno uvnitř uzlem) | B obsah |
| `database/schema/project_schema.py` → `project_settings` | project.sqlite | cíl a platforma projektu | ano | B obsah |
| `database/schema/project_schema.py` → `desktop_v3_state` | project.sqlite | paměť projektu pro agenty: settings, rules, decisions, uzly, tikety | ano | B obsah |
| `registry.sqlite` | `projects`, `project_sources`, `workspaces`, `jobs` | seznam projektů a jejich druh zdroje | napříč projekty | B obsah |

Závěr: žádná preference vzhledu ani ovládání není uložena per projekt. Skupina C (sporné) je prázdná.

## Odkud tedy plynou rozdíly mezi projekty

Rozdíly nevznikají z uložených dat, ale z **větvení chování podle druhu zdroje projektu** (`sourceKind`: `git`, `local`, `empty`, `builtin`). Do 2026-09-15 bylo toto větvení rozepsáno na čtyřech místech v `frontend/app/components/App.tsx` a odvozené příznaky (`localProject`, `legacyFreeNode`) tekly do `TopBar`, `ScopeContext`, `ProjectSection` a do dialogu pracovního prostoru.

Co se liší podle druhu:

- git projekt: horní lišta nabízí main a oddělené pracovní prostory, nastavení projektu nabízí synchronizaci upstreamu, otevírá se do `main`;
- lokální složka, prázdný projekt, vestavěný návrh: bez větví a worktree, otevírá se do `draft`;
- vestavěný draft navíc smí mít volné uzly bez sektoru (historické chování).

## Co se změnilo

Větvení je nyní na jediném místě: `frontend/shared/project-capabilities/logic/project-capabilities.ts` (test vedle). `App` z něj spočítá schopnosti projektu a rozdá je dílkům v props. Žádný dílek si druh projektu nevyhodnocuje sám. Nový projekt libovolného druhu se proto chová přesně jako každý jiný projekt téhož druhu a změna chování se dělá v jednom souboru.

Pravidlo pro další práci je v `docs/pravidla-struktury.md`, sekce „Jedno rozhraní pro všechny projekty“.
