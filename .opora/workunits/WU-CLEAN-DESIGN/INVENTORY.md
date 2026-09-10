# Inventura akcí Canvasu (před přeskupením)

Surface: **COMMAND / INSPECT** (primární), Explore sekundární (Mapa). Legenda „domov“: T = horní lišta, M = menu Nastavení v horní liště, R = levý rail módů, H = hlavička obsahu, I = inspektor (pravý kontext), F = stavový řádek, D = dialog.

| Akce (dnes) | Účel | Nový domov | Kdy je dostupná | Skutečný handler / API |
|---|---|---|---|---|
| Select „Projekt“ | přepnout projekt | T | vždy, ne při busy | `selectProject` → `/api/view` |
| „Nastavení projektu“ | zpět na hub (zadání, LLM, coding) | M | vždy | `setScreen("home")` |
| „Odebrat repozitář“ | odebrat git projekt z aplikace | M (danger) | jen git projekt | `/api/removal-preview` → dialog → `/api/remove` |
| „Nastavení plochy“ | mřížka, snap, kreslicí mřížka | M → D | vždy | `localStorage` (`SETTINGS_KEY`) |
| `LOKÁLNĚ · port` | doklad lokálního běhu | T (desktop) | vždy | `location.port` |
| „Čistý main“ / „Pracovní prostor“ | přepnout main ↔ worktree | T (segment) | jen git projekt | `setWorkspace` → `/api/view` |
| Select „Pracovní strom“ | vybrat konkrétní worktree | T | jen když je worktree aktivní | `setWorkspace` |
| branch · sha, „Pracovní soubory změněny“ | stav revize | T (chip) | git projekt | `view.branch/sha/dirty` |
| „Obnovit pohled“ | refetch | M | vždy | `refresh()` |
| „Synchronizovat main“ | fetch spravované kopie, bez push | M | git projekt, s `confirm` | `/api/sync` |
| Rail Struktura/Text/Kreslení/Mapa | přepnout mód | R | vždy | `setMode` (URL `mode=`) |
| Strom vrstev (levý panel) | navigace vrstvami | zrušen; nahrazen drobečkem H + kartami na plátně | – | `enter(id)` |
| „Zdroj pohledu“, „Oddělený adresář“, „Operace“ | kontext scope | I (stav bez výběru) | vždy | `view.source/observedAt`, `workspaces`, `jobs` |
| Mapa: počty, „Propojit z/do“, „Propojit uzly“, „Export pro Archify“ | vazby napříč vrstvami, export | I v módu Mapa | Mapa; propojení jen editable | `connectGraph` → `/api/graph`; `downloadArchify` |
| Nástroje kreslení + Wireframe paleta | volba nástroje, vkládání rámů | I v módu Kreslení | Kreslení, editor připraven a editable | `setDrawingCommand`, `wireframeInsert` |
| Drobeček „Projekt / …“ | návrat výš | H | vždy | `enter` |
| „Vazby mimo vrstvu: N“ | skok do mapy | H | Struktura, N>0 | `setMode("map")` |
| „+ Sektor“ / „+ Uzel“ | vytvořit (dialog) | H | Struktura/Text, editable | `/api/graph` |
| Dvojklik na plátno / název | vytvořit na místě, přejmenovat | plátno | editable | `/api/graph` |
| Prázdné plátno (hero, symbol) | nápověda | tichý stav v plátně, bez hero | prázdná vrstva | – |
| Inspektor idle „Celý systém…“ + flow-rule | dekorace | zrušeno; nahrazeno kontextem scope | – | – |
| Uzel: „Otevřít vnitřní plátno“ | zanořit | I hlavička (primární) | uzel vybrán | `enter` |
| Uzel: „Smazat uzel/sektor“ | odstranit s náhledem dopadu | I patička (danger) | editable | `/api/removal-preview` → `/api/remove` |
| Uzel: „Připravit úkol pro agenta“ | scope pro agenta, žádný běh | I hlavička | uzel vybrán | `emitAgentTask` (event, bez API) |
| Uzel: bloky + „Zdrojový text“ + „Uložit text“ | dokument uzlu, autosave bloků, ruční zdroj | I · karta Obsah | vždy; zápis jen editable | `/api/node-text` (CAS, pending edits) |
| Uzel: Souvislosti | odkazy/hrany | I · karta Obsah | pracovní prostor | `/api/node-links` |
| Uzel: „Podstata“ + potvrzení + „Uložit podstatu“ | proč uzel existuje | I · karta Zadání | editable, dirty | `/api/graph` |
| Uzel: Zadání (Cíl, Co není, Podmínky) + „Uložit zadání“ | zadání pro práci | I · karta Zadání | dle `node-spec.readOnly` | `/api/node-spec` (CAS, drafts) |
| Uzel: pracovní prostory + „Připravit oddělený worktree“ | doložené worktree | I · karta Práce | vždy; tvorba jen git | `/api/workspaces` |
| Uzel: aktivita agenta (NodeActivity) | vazby běhů, journal | I · karta Práce (mount až při otevření karty) | vždy; **API `/api/agents` v této bázi chybí → poctivá chyba** | `/api/agents/bindings`, `/activity`, `/unbound` |
| Běh → detail zdroje (AgentsWorkspace) | běhy, zdroje, 4 vrstvy (prompt/kontext/verifikace/iterace) | nový mód „Běhy“ v R, obsah | vždy; API chybí → chyba, nic se nespouští | `/api/agents/sources`, `/runs`, `/runs/{id}` |
| Vazba: „Smazat vazbu“ | odstranit hranu | I | editable | `/api/removal-preview` → `/api/remove` |
| Text mód: dokument vrstvy + děti, „Zanořit“ | psaní/outliner | obsah | vždy | `/api/node-text` |
| Text mód: Souvislosti / Deník (taby vpravo v obsahu) | kontext vrstvy, datovaný zápis | I (taby) | Text mód s vrstvou | `/api/node-links`, `/api/node-journal` |
| Stavový řádek | počty, read-only, „agent se nespouští“ | F | vždy | odvozeno z `view` |
| Dialogy: GitHub, worktree, nový uzel | vstupy s potvrzením | D | dle stavu | `/api/connect`, `/api/workspaces`, `/api/graph` |

## Guardy, které zůstávají beze změny
- CAS na text/deník/zadání/kresbu, pending-edits v sessionStorage a flush při odchodu (WU-EDIT-SAFETY se nepřepisuje).
- Žádná akce UI nespouští placený běh; „úkol pro agenta“ jen vydává scope.
- Main je jen ke čtení; tlačítka zůstávají viditelně disabled s titulkem, ne skrytá.
- Odebrání/smazání vždy přes náhled dopadu a potvrzení.
- Nedostupné API (`/api/agents` v této bázi) se ukazuje jako chyba s HTTP stavem, ne jako prázdný úspěch.
