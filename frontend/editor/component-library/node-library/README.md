Výběr uzlu otevírá pouze pravý detail. Původní automatická levá knihovna uzlu (`NodeLibraryDrawer`, `LibraryContext`, `logic/library-model.ts`) byla odebrána, protože ji App nepřipojoval.

Blok přidává tlačítko na kartě, akce a podklady se ovládají přes porty karty; kontext a uložené zadání jsou v pravém detailu. Explicitní výběr konkrétního bloku otevírá `editor/block-editor/components/BlockEditorDrawer` se stávajícím editorem. Zavření vrací výběr na uzel. Katalog Knihovna → Prvky / Struktura zůstává samostatným menu otevřeným uživatelem.

Ze složky zůstávají jen styly `styles/node-library.css`, které používá úzký obal editoru konkrétního bloku (`BlockEditorDrawer`). Žádná uložená data se touto změnou nemažou ani nepřevádějí.
