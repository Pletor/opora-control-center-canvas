Výběr uzlu otevírá pouze pravý detail. Původní automatická levá knihovna uzlu (`NodeLibraryDrawer`, `LibraryContext`, `logic/library-model.ts`) byla odebrána, protože ji App nepřipojoval.

Blok přidává tlačítko na kartě, akce a podklady se ovládají přes porty karty; kontext a uložené zadání jsou v pravém detailu. Explicitní výběr konkrétního bloku otevírá boční menu bloku `editor/block-panel/components/BlockPanelDrawer` se stopou práce karty. Zavření vrací výběr na uzel. Katalog Knihovna → Prvky / Struktura zůstává samostatným menu otevřeným uživatelem.

Ze složky zůstávají jen styly `styles/node-library.css`, které používá obal bočního menu konkrétního bloku (`BlockPanelDrawer`, varianta `node-library--wide`). Žádná uložená data se touto změnou nemažou ani nepřevádějí.
