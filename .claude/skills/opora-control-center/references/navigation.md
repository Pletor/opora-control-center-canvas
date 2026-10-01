# Projekt a navigace

## Nezaměň tři druhy kontextu

1. **Git checkout aplikace** — repozitář, ze kterého vyvíjíš OPORA samotnou.
2. **Projekt uvnitř OPORA** — ID z `/api/bootstrap`, nikoli název složky.
3. **Workspace projektu** — `draft`, `main` nebo skutečné ID pracovního stromu.
   Git main aplikace může být zapisovatelný; API workspace main Git projektu
   je v aplikaci běžně jen pro čtení. Autoritou je `view.readOnly`.

Spusť `opora_read.py ... status`, poté `projects`. Pro zvolený projekt spusť
`workspaces --project ID`; teprve potom `view --project ID --workspace ID`.
Návrhy builtin/local/empty používají typicky `draft`; Git projekty mají main
nebo spravované workspaces. Není-li ID jasné, nevol náhodný projekt.

## Pracuje se v originále, ne v kopii

Projekt se připojuje jako **lokální složka na originální cestu**, kterou má uživatel
otevřenou ve VS Code (ta má origin na GitHubu). Žádný klon v `.data` ani git worktree:

- Připojení: `POST /api/local-project` `{name, path, confirmed: true}`, kde `path` je
  absolutní cesta. V JSON piš lomítka (`I:/…/ample`), protože zpětné lomítko by bylo neplatné escapování.
  Stejná cesta podruhé vrátí existující projekt.
- Plátno, zadání a karty žijí v OPORA (`.data/production/projects/<id>/`). Do repa
  projektu se nezapisují a na GitHub se nedostanou. `.data` je mimo git, takže nemají zálohu.
- Kód upravuje uživatel nebo agent přímo v originále. Větve, commity a push dělá on
  ve VS Code. Aplikace u lokálního projektu žádnou git operaci nedělá.
- Lokální projekt má jen workspace `draft`, „Vytvořit worktree“ a „Synchronizovat main“
  se ho netýkají.

Odpojení projektu: `GET /api/removal-preview?project=ID&workspace=main&kind=project&target=ID`
→ `POST /api/remove` `{project, workspace: "main", kind: "project", target, digest, confirmed: true}`.
Jde jen o záznam v archivu, soubory projektu v `.data` zůstanou. Odpojení i mazání složky
dělej jen na výslovný pokyn. `project.sqlite` drží běžící aplikace otevřený, takže ho smažeš až po jejím zastavení.

## UI

- Horní výběr **Projekt** určuje společný scope.
- **Projekt / Editor / Live Run** jsou prostředí stejné aplikace.
- Projekt: vlevo kompaktní strom s hledáním, viditelností a filtry cest; vpravo uložené Archify HTML. Z této stránky jsou odstraněny dokumentový editor, paměť, přidávání referencí i společný kontext. Tyto změny nemažou data projektu.
- Layout a definice filtrů mají jeden zdroj: `frontend/project/shell/components/ProjectLayout.tsx` a `frontend/project/shell/styles/project-layout.css`. `ProjectWorkspace` jen skládá tento layout a sdílený `ArchifyMap`; strom používá existující `SourceExplorer` v kompaktní variantě. Horní lišta zůstává sdílený `TopBar`. Staré třísloupcové projektové styly se nepoužívají.
- `Archify` / `Graphify-out` přepínají aktivní mapu projektu: uložené HTML z `archify-out/` nebo `graphify-out/` hlavního projektu (viz `archify.md`, `graphify.md`). Filtry třídí názvy/cesty, ne obsah souborů.
- Editor: hlavní canvas, uzly, vrstvy, text, kresby, práce s podklady.
- Live Run: skutečné dostupné sessions, výstupy, stav a omezené ovládání.
- U Git projektů: **Čistý main**, **Pracovní prostor**, výběr **Pracovní strom**.
- **Nastavení** vlevo dole → Obecné / Plátno / Projekt / Skills / Connectors.
  V Obecné je i globální „Automatická aktualizace map po mergi do main“.
  Synchronizovat main (sekce Projekt) se týká spravované kopie; není to push na GitHub.

Naviguj podle role a textu ovládacího prvku, ne podle starých pixelových souřadnic.
Po každé změně projektu/workspace znovu načti aktuální stav; starý vybraný uzel
ani odpověď dřívějšího API požadavku nesmí přejít do nového kontextu.

## Přímé odkazy

Přesný odkaz může sestavit skript `view` (vrací `links`). Podporovaná pole:
`screen=canvas`, `project`, `workspace`, `environment=project|editor|live`,
`mode=structure|text|drawing|map`, `layer` pro vnitřní plátno.
Příklad: `/?screen=canvas&project=ID&workspace=draft&environment=editor&mode=structure`.
ID URL-enkóduj, nekonstruuj URL neescapovaným názvem projektu.

Filtrace stromu není mazání. Skryté/ignorované soubory nepřidávej automaticky
mezi reference; obsah `.env`, klíče a autentizační soubory se nepřikládají.
