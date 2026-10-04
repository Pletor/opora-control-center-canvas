Výběr uzlu otevírá pouze pravý detail. Původní automatická levá knihovna uzlu (`NodeLibraryDrawer`, Bloky / Akce / Podklady / Kontext) již není v App připojená; její model a původní dílky zůstávají zachované pro kompatibilitu.

Blok přidává tlačítko na kartě, akce a podklady se ovládají přes porty karty; kontext a uložené zadání jsou v pravém detailu. Explicitní výběr konkrétního bloku otevírá `editor/block-editor/components/BlockEditorDrawer` se stávajícím editorem. Zavření vrací výběr na uzel. Katalog Knihovna → Prvky / Struktura zůstává samostatným menu otevřeným uživatelem.

`logic/library-model.ts` obsahuje původní stav panelu, předlohy bloků `addBlockOfKind` a kontroly kontextu `contextChecks`, `linkedBlockPorts`; testy jsou vedle modelu. Styly `styles/node-library.css` využívá také úzký obal editoru konkrétního bloku. Žádná uložená data se touto změnou nemažou ani nepřevádějí.
