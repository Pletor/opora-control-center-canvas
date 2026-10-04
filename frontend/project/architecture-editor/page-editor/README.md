# Editor stránky

Krok 3 kontraktu `docs/architektura-projektu.md`: rychlá infografika jedné stránky ve čtyřech sloupcích (grid).

1. **Levý panel (280 px)** – záložky *Strom projektu* (`project-tree/`) a *Knihovna prvků* (`ArchitectureCatalog`): rodiny Frontend, Backend, Databáze, Security, Testy, Cache, Cloud a infrastruktura (`logic/library-families.ts`) jako barevně orámované skupiny s počtem a sbalením, dlaždice po třech, hledání, přetažení na mapu i tlačítko „Vložit“.
2. **Mapa architektury** (`ArchitectureCanvas` + `map-card/`) – oblasti, sektory a uzly otevřeného rozsahu stránky. Barva karty podle `card.layer` (sektor bez vrstvy = frontend), porty vlevo/vpravo, vazby barvou zdroje se šipkou, `flow` přerušovaně (`logic/canvas-model.ts`). Dvojklik nebo „Otevřít detail ↗“ otevře Hierarchický editor.
3. **Hierarchický editor komponenty** a 4. **Detail prvku (300 px)** – PageEditor je nevytváří; rodič `ArchitectureEditor` je složí (`component-structure/`, `element-detail/`) a předá jako sloty `structure` / `detail`. Sloupec se ukáže jen, když slot není `null`.

Šířku řeší CSS (`logic/page-layout.ts` skládá jen BEM varianty): pod 1400 px se mapa a struktura střídají přepínačem „Mapa / Struktura“, pod 1050 px vyjede detail zprava jako zásuvka.

Dílek nic neukládá: všechny změny (vložení, přesun, vazba, nový uzel / sektor / oblast, „+ Stránka“) hlásí callbackem rodiči. „+ Stránka“ v Stromu přepne na Mapu projektu dané domény – strukturu stránek mění jen ona. React Flow při přestavbě uzlů přenáší `measured`, jinak by se karty znovu měřily a vstupy ztrácely fokus. Pohled plátna se pamatuje v `localStorage` podle ID editoru a rozsahu.

Testy: `logic/*.test.ts`, `project-tree/logic/project-tree-model.test.ts` (`npm test`).
