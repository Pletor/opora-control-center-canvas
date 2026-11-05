Dílna Pletora: kde člověk píše skilly a měřitelné deterministické funkce (kontrakt `docs/navrhy/2026-11-05-dilna-skillu.md` §2a, §3a, §5).
Otevírá se ze záložky **Dílna** v nastavení Pletora (ozubené kolo, `PletorSettingsPanel`) jako celoobrazovková vrstva, protože dva editory vedle sebe se do malého panelu nevejdou. Esc nebo „Zavřít“ ji zavře (s neuloženou změnou nejdřív jen varuje) a focus se vrátí na „Otevřít dílnu“.

Dílky (`components/`):

- `PletorWorkshop`: rodič a vrstva (`role="dialog"`). Drží `useWorkshop`, skládá lištu (stav, Obnovit, Zavřít), levý sloupec a dvě okna editoru.
- `WorkshopList`: seznam (Skilly nebo Funkce) jako tlačítka a pod ním „Nový skill“ / „Nová funkce“: pole se jménem a Založit (aktivní jen pro platné jméno `^[a-z][a-z0-9-]*$`).
- `WorkshopSkillEditor`: výběr souboru skillu (`files`), textarea souboru, Uložit (aktivní jen při změně).
- `WorkshopToolEditor`: textarea `<nazev>.py`, textarea `<nazev>.cases.json`, Uložit a Změřit (měří uloženou funkci, s neuloženou změnou je vypnuté), pod nimi `WorkshopMeasure`.
- `WorkshopMeasure`: `passed/total`, trvání, štítek deterministická / NEdeterministická, selhání (název, dostal, čekal jako JSON) a `error`.
- `WorkshopPending`: inline varování „Neuložená změna“ se Zahodit / Zůstat, když člověk přepíná skill, soubor nebo funkci s neuloženou změnou v témže editoru. Žádné blokující dialogy.

Logika (`logic/`):

- `workshop-api.ts` (test vedle): volání přes `api()` a odolné čtení odpovědí (chybějící pole = prázdné, položky bez jména pryč).
- `workshop-state.ts` (test vedle): čistý stav dvou editorů: otevřený skill a funkce (uložené vs. rozepsané), `askSwitch` / `discard` / `keep` pro odložený přechod, poslední měření (nová funkce ho smaže), `defaultFile` (SKILL.md), `NAME_RE`, `measureLine`.
- `use-workshop.ts`: React hook nad tím (seznamy, načtení, uložení, měření, založení, jedna řádka hlášení, `busy`).

Kontrakt API (`/api/pletor/workshop`):

- `GET skills` → `{skills:[{name, description, files}]}`; `POST skills` `{name}` (409 existuje, 422 název)
- `GET skills/{name}/file?path=…` → `{path, content}`; `PUT skills/{name}/file` `{path, content}` → `{path, bytes}`
- `GET tools` → `{tools:[{name, path, cases}]}`; `POST tools` `{name}` založí šablonu (409/422)
- `GET tools/{name}` → `{name, code, cases}` (`cases` je syrový text JSON); `PUT tools/{name}` `{code, cases}` → `{name, cases}` (422 s důvodem při vadném JSON)
- `POST tools/{name}/measure` `{}` → `{name, passed, total, failed:[{name, got, expected}], durationMs, deterministic, error}`

Nice-to-have, zatím ne: čísla řádků v editoru, kódový editor (CodeMirror až po schválení závislosti), panel Oprávnění / Testy / Verze a akce Aktivovat / Vrátit z §5.

Styl: `styles/pletor-workshop.css`, blok `pletor-workshop`, zelené proměnné `--pletor-*` z `frontend/pletor/styles/pletor.css`.
