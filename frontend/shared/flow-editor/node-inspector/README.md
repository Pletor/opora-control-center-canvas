# Inspektor uzlu

`NodeInspector` je postranní panel vybraného uzlu: id, typ a verze typu, stav ve vybraném běhu (pokus, model, tokeny, cena, čekání, prostoj, chyba) a záložky Parametry / Vstup / Výstup (`input_ref` / `output_ref`). `ParamFields` kreslí pole podle druhu hodnoty a zápis ověří (`logic/inspector-fields.ts` + test); změnu hlásí `onParam(key, value)`, `undefined` parametr odebere. V režimu běhu je jen ke čtení.
