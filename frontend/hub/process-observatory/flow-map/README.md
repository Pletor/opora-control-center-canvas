# flow-map — mapa toku Živého procesu

Řádek na kartu (`Lane` z `../logic/lanes.ts`), sloupce = sedm fází (Zadání … Paměť). Značka pracovníka stojí
ve fázi poslední události, stopa za ní nese stav poslední události každé minulé fáze (plný kruh potvrzeno,
kosočtverec selhalo, dutý kroužek čeká, šedý kruh proběhlo bez potvrzení, čárkovaný bez události).
`logic/marker-motion.ts` rozhoduje o pohybu (přesun / pulz / zatřesení) jen podle nové události. Klik na řádek
hlásí `onSelect` nahoru.
