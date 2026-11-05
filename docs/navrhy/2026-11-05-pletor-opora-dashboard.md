# AGI_Pletor: pevná stránka `pletor_opora_dashboard`

Stav: návrh ke schválení (2026-11-05). Navazuje na `2026-11-04-pletor-jarvis.md`, `2026-11-04-pletor-nastaveni-llm.md`, `2026-11-05-dilna-skillu.md`, `2026-11-05-budovatel-zameru.md` a `2026-11-04-platno-monitoringu.md`.

## 1. Co to je

**AGI_Pletor** je modul, ve kterém žije vše kolem Pletora a srdce: mozek, hlas, podklady, Dílna, stav srdce, monitoring, nastavení a eval. Má **jednu pevnou stránku** `pletor_opora_dashboard` (adresa `?screen=pletor`), která je k dispozici vždy, nezávisle na projektu a plátnech. Dnes jsou tyto věci rozsypané: HUD přes celou obrazovku, nastavení za ozubeným kolem v malém popupu (Mozek a čtení / Hlas / LLM / Dílna), stav srdce v okně asistenta, monitoring na plátně 4.

Zelený HUD (kokpit) zůstává jako start OPORY a hlasový vstup. Dashboard je **velín pod ním**: tlačítko v liště HUD „Velín“ vedle ozubeného kola, Esc zpět.

## 2. Kde to žije

- Backend: `backend/agi_pletor/` (přejmenované `backend/pletor/`, probíhá v jiné relaci) + `pletor_opora_settings/` (Dílna: `skills/`, `tools/`; připravené složky `connectors/`, `mcp_servers/`, `dev_github/`) + `pletor_canvas_1/` (vazba na plátno srdce). Routy: `backend/api/pletor/` (`pletor_routes.py`, `workshop_routes.py`, nově `dashboard_routes.py`).
- Frontend: nová feature složka `frontend/pletor-dashboard/` (dílky, logika s testy, BEM styl `pletor-dashboard__…` v zeleném HUD rytmu). Dnešní `frontend/pletor/` (HUD, hlas, okno) a `frontend/pletor-workshop/` (Dílna) zůstávají a dashboard je skládá.

## 3. Části stránky (levá navigace, jedna aktivní část)

| Část | Co ukazuje | Z čeho se skládá (už existuje) | Nové |
|---|---|---|---|
| **Přehled** | mozek, hlas, stav srdce, eskalace, poslední rozhovor, stav hostů; jedna obrazovka „jak se organismu daří“ | `GET /api/pletor/state` (brain, heart, escalations), `/voices`, `monitor_state.json` | složení do karet, `GET /api/pletor/dashboard` (jeden souhrn) |
| **Mozek a LLM** | volba mozku (Claude / Ollama, model), Claude Code, Codex, Ollama, cswap | `PletorSettingsLlm`, `POST /brain`, `GET /llm` | zápis modelů (M2 z kontraktu LLM) |
| **Hlas** | enginy, hlasy, kvóta ElevenLabs, přerušení hlasem, konec věty | `PletorSettingsVoices`, `/voices`, `/tts` | nic |
| **Srdce** | stav, fronta po prostorech, posledních 20 dávek, deník, eval gate a verze promptu z Brainu | `heart.status`, `brain_registry` | `GET /api/pletor/heart` (souhrn jako v zahozeném velínu, jen čtení) |
| **Podklady** | co Pletor právě vidí (blok PODKLADY po sekcích se stropy), Schránka, rozhodnutí | `context.build_context` | `GET /api/pletor/context` (náhled bloku, jen čtení) |
| **Dílna** | skilly a měřitelné funkce (dva editory) | `PletorWorkshop` (PR #343) | později generování modelem (D5) |
| **Monitoring** | hosté a stavy, události plátna 4 | `backend/monitoring/`, `log_canvas` | čtení událostí plátna 4 (dnes chybí čtecí funkce) |
| **Rozhovor** | historie Pletora po projektech, hledání, export | `messages.jsonl` | `GET /api/pletor/messages?project&limit` |
| **Nastavení** | konektory, MCP servery, GitHub pro vývoj (připravené složky), přístup zvenku | `pletor_opora_settings/*` | až podle obsahu těch složek |

## 4. Pravidla

- Dashboard **jen čte a nastavuje**; práci zadává Pletor, plátno píše srdce (beze změny).
- Jedno rozhraní pro všechny projekty: dashboard je per aplikace, projekt je jen filtr tam, kde dává smysl (Srdce, Podklady, Rozhovor).
- Žádné duplikáty: část = existující dílek, dashboard ho jen umístí. Popup za ozubeným kolem se po dostavbě zmenší na zkratku „Velín“.
- Soubory do ~200 řádků, logika bez Reactu s testy, BEM s příběhem.

## 5. Milníky

| | Co | Hotovo, když |
|---|---|---|
| **V1** | Stránka `?screen=pletor`, levá navigace, části **Přehled**, **Mozek a LLM**, **Hlas**, **Dílna** z existujících dílků; tlačítko Velín v HUD | Z HUD se dostanu do velínu a zpět, čtyři části fungují |
| **V2** | **Srdce** a **Podklady** (jen čtení) | Vidím stav, frontu, dávky a blok PODKLADY |
| **V3** | **Rozhovor** a **Monitoring** | Historie po projektech, události plátna 4 |
| **V4** | **Nastavení** (konektory, MCP, GitHub) a zápis modelů (LLM M2) | Nastavení LLM a konektorů jde měnit z velínu |

## 6. Otevřené otázky

- **Kolize s rozpracovanou stránkou nastavení** (`frontend/settings/SettingsPage.tsx`, jiná relace): má skupinu „PLETOR A SRDCE“ (Přehled organismu, Modely a účty, Jev). Návrh: nastavení OPORY zůstane obecné (rozhraní, plátna, projekt, Jev) a vše o Pletorovi a srdci se přesune do dashboardu, aby věc žila na jednom místě. Rozhodnout dřív, než se obě sloučí.
- Název na obrazovce: „Velín“ (krátké, sedí k HUD), nebo „AGI Pletor“?
- Má HUD po otevření velínu zůstat jako plovoucí okno (jako dnes při „Vstoupit do OPORY“), aby šlo dál mluvit? Návrh: ano.
