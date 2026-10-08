# Karta DNA

Jediný nativní dialog pro otevřenou kartu. Plátno drží jen kompaktní orientační obraz; detail se odmountuje po zavření.

- `components/CardDnaDialog.tsx` – modal a sedm ARIA záložek, mountuje vždy pouze aktivní obsah.
- `components/CardDnaDetail.tsx` – skládá Přehled, Zadání, Proces, Workflow, Důkazy, Kód a DNA z existujících editorů.
- `components/NodeSpecHistory.tsx` – lazy historie revizí zadání.
- `logic/` – chronologie procesu, filtrování a přenositelný Markdown DNA.
- `styles/card-dna.css` – jediný BEM styl dialogu i kompaktního obrazu.
- `logic/draft-guard.ts` – zavření, přepnutí panelu a skrytí editoru až po vyřešení save scope.
- `logic/card-click.ts` + `use-dialog-opening.ts` – browser detail místo časovače;
  náhled nebere kartě druhý click, po opuštění karty přejde na showModal.
- `logic/history-pagination.ts` – dokončení všech stránek, chyba i odmountování zachovají pravdivý stav.

Rodič (`Board`) vlastní otevřenou kartu a pouze předává data/callbacky. `App` je jediný, kdo uloží změnu uzlu z editoru kontrol. Proces používá stránkovanou historii výsledků agentů; ostatní síťové čtení se spouští až po aktivaci příslušné záložky.
