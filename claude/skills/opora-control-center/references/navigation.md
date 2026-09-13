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

## UI

- Horní výběr **Projekt** určuje společný scope.
- **Projekt / Editor / Live Run** jsou prostředí stejné aplikace.
- Projekt: vlevo kompaktní strom s hledáním, viditelností a filtry cest; vpravo uložené Archify HTML. Z této stránky jsou odstraněny dokumentový editor, paměť, přidávání referencí i společný kontext. Tyto změny nemažou data projektu.
- Layout a definice filtrů mají jeden zdroj: `src/ProjectLayout.tsx` a `src/project-layout.css`. `ProjectWorkspace` jen skládá tento layout a sdílený `ArchifyMap`; strom používá existující `SourceExplorer` v kompaktní variantě. Horní lišta zůstává sdílený `TopBar`. Staré třísloupcové projektové styly se nepoužívají.
- `Graphify-out` je zatím neaktivní položka layoutu, nikoli napojený renderer nebo spuštění skillu. Filtry třídí názvy/cesty, ne obsah souborů.
- Editor: hlavní canvas, uzly, vrstvy, text, kresby, práce s podklady.
- Live Run: skutečné dostupné sessions, výstupy, stav a omezené ovládání.
- U Git projektů: **Čistý main**, **Pracovní prostor**, výběr **Pracovní strom**.
- **Nastavení** → Nastavení plochy / Nastavení projektu / Obnovit pohled.
  Synchronizovat main se týká spravované kopie; není to push na GitHub.

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
