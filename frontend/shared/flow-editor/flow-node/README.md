# Uzel toku

`FlowNodeCard` je karta uzlu React Flow: tvar podle role (`../logic/node-role.ts`), stav běhu (rámeček, odznak, čekání s důvodem, prostoj, cena), značka rozdílu verzí, připnutý výstup a chybějící povinný port. `FlowPort` kreslí handle podle `kind` portu (kruh hlavního toku, kosočtverec sub-portu), popisek s hvězdičkou povinnosti a „+“ u prázdného portu. „+“ jde na plátno přes `logic/port-actions.ts` (kontext), protože uzel React Flow nedostává props od rodiče přímo. Styl `styles/flow-node.css`.
