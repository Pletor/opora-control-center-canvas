# Editor — sektor, uzel, text a kresba

## Vytvořit sektor

1. Vyber projekt a zapisovatelný workspace, v Editoru mód **Struktura**.
2. `+ Sektor` → `Název uzlu`.
3. U připojeného projektu výslovně zvol původ:
   - **Jen funkce / myšlenka, bez souboru**: vyplň `Co má tato část umět?`.
     Vznikne koncept bez sourceRef, žádný adresář na disku.
   - **Navázat na existující zdroj**: zvol skutečnou složku v nabídnutém stromu.
   - **Navrhnout nové**: `Podstata návrhu sektoru` alespoň 12 znaků;
     zamýšlená cesta je nepovinná a nic nevytváří na disku.
4. `Vytvořit`, potom ověř sektor v grafu/API. Builtin Lokální návrh umožňuje
   také volný sektor bez volby zdroje.

## Vytvořit uzel uvnitř sektoru

- Buď vyber sektor → **Otevřít vnitřní plátno** → `+ Uzel`,
- nebo `+ Uzel` z vnější vrstvy → vyber **Cílový sektor**.
- Vyplň název, původ a příslušný popis/zdroj. Samotný výběr sektoru nemusí
  nahradit povinnou volbu původu a popis.
- Koncept může mít sektor jako rodiče, aniž získá filesystem sourceRef.
- Existující zdroj uzlu lze navázat pouze uvnitř sektoru s existujícím zdrojem.
- Plánovaný soubor/složka může mít relativní cestu uvnitř sektoru. Pokud sektor
  cestu ještě neurčuje, ponech cestu uzlu neurčenou; nic nevymýšlej.
- `Vytvořit` musí skončit uložením uzlu se správným `parentId`. Název sám není
  identita; ověř konkrétní node ID.

### Když je Vytvořit neaktivní

Zkontroluj postupně: probíhající uložení, název, zapisovatelnost, sektor,
původ zdroje, popis, vybranou existující cestu či kompatibilní plánovanou cestu.
Novější formulář zachovává návrh při změně sektoru, ale existující cestu je
nutné znovu vybrat v novém rozsahu. Neodstraňuj atribut disabled přes JS.
Je-li vše splněno a problém trvá, je to bug: viz `bugfix.md`, nikoli obcházení UI.

## Dokumentace uzlu

- **Obsah**: bloky uzlu a zdrojový text. Bloky mají odložené automatické uložení;
  textové pole `Text uzlu` ruční `Uložit text` nebo Ctrl+S. Počkej na uloženou verzi.
- **Zadání**: `Cíl práce`, `Co není součástí`, `Podmínky dokončení` → `Uložit zadání`.
- **Práce**: skutečná aktivita a navázané pracovní prostory, nikoli vymyšlený běh.
- Desktop workflow: fáze `discover → define → build → verify → live`, kritéria a kroky.
  Zaškrtnutí není důkaz implementace. Změň stav jen podle reálného výsledku.

Před přechodem jinam čekej na potvrzení uložení. „Zahodit rozepsané…“ maže draft:
nepoužívej tuto akci jako obecnou opravu konfliktu bez souhlasu uživatele.

## Canvas a kreslení

Módy **Struktura**, **Text**, **Kreslení**, **Mapa** pracují s propojeným projektem.
Vnitřní plátno mění vrstvu, breadcrumb vrací k předkům. Mapa zobrazuje širší graf.
Kreslení a wireframe patří konkrétní vrstvě. Nativní kreslicí inspektor není totéž
co inspektor uzlu. Přepnutí wireframe nesmí být podmínkou běžné editace tvarů.
Ukládej kresbu a ověř její revizi před přidáním do podkladů pro agenta.

Smazání řeš náhledem dopadu a konkrétním potvrzením; nemaž celý graf jen proto,
že má obsahovat nový uzel. Při API zápisu zachovej všechny ostatní uzly a vazby.
