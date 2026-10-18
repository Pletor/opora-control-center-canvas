# Karta Mapy architektury

Uzel React Flow pro Editor stránky. Oblast je přerušovaný jantarový rám s hlavičkou „OBLAST: …“, počtem sektorů (geometrické členství, `membersOf`) a „+ Sektor“. Vybraná oblast má tahadla na hranách a rozích (`NodeResizer`, 120–20 000 px); ustálený rozměr hlásí `actions.resizeArea`, plátno ho pošle rodiči a ten ho uloží jako `size` uzlu. Sektor / uzel je karta v barvě své vrstvy: ikona v rámečku, druh, název, účel, štítek „N uzlů“, menu ⋮ (Otevřít detail, Otevřít v Editoru), až tři potomci jako řádky a „+ Přidat komponentu“. Porty vlevo (vstup) a vpravo (výstup) jsou barevné kroužky.

Karta dostává hotová data (`cardSummary`, `areaSectorLabel` z `../logic/canvas-model.ts`) a stabilní `actions`, které plátno směruje na aktuální callbacky rodiče. Nic neukládá.
