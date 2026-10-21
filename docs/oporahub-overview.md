# Jednostránkový přehled OporaHubu

> Fáze 2: výchozí stránku nahradilo rozhraní nad jedním dokumentem agent-state
> (smyčka, karta, pro agenty) popsané v [oporahub-ui.md](oporahub-ui.md). Pravidla níže
> (přesný výběr, ✕/Esc, žádné vymyšlené stavy) platí dál pro všechny detaily.

Uživatel potřebuje na jedné stránce poznat, co se děje, co čeká na člověka
a co udělají agenti dál. Výchozí obrazovka proto nesmí být dlouhá řada formulářů.
Claude Code s dovedností frontend-design vytvořil [klikací HTML artefakt](design/README.md);
produkční rozhraní musí vycházet ze skutečných modelů a používat dosavadní API.
Ukázková data v návrhu nejsou živá telemetrie.

## Výchozí stránka

- Zůstává společná navigace Projekt / Editor / OporaHub a výběr projektu/prostoru.
- Přijatý plán: krátká revize, rozdíl pracovní verze a srozumitelný další krok.
  Chybějící základ vyzve k jeho prohlédnutí a přijetí, nepředstírá platný plán.
- Potřebuje rozhodnutí: konkrétní návrhy grafu a zadání, autor, název a dopad.
  Tlačítko otevře přesně vybraný návrh, nikdy ho rovnou nepřijme.
- Práce agentů: karty, skutečný uložený vlastník, stav oprávnění a další krok.
  Chybějící vlastník se označí jako neznámý; jméno ani aktivita se nevymýšlejí.
  Nahlášený výsledek se zřetelně liší od nezávislého ověření a dokončení.
- Důkazy a review: pozorovaný stav PR, pravidla review a zdraví sledování
  zůstávají oddělené. Merge není automaticky ověřená nebo nasazená práce.
- Poslední činnost je složená z doložených událostí s časem a původem.
  Nedostupné zdroje nesmějí vytvářet události ani zelené souhrny.
- Nový návrh, pravidla běhů, historie a rozhraní pro agenty jsou dostupné jako
  cílené akce. Obsah se zobrazí v detailu, ne jako výchozí nekonečný formulář.
- Formální podklady otevřou [historii TLC/Lean](oporahub-verification.md):
  konkrétní tvrzení, předpoklady, meze a původní soubory. Nahlášený úspěch
  neuděluje nezávislé ověření; chybějící podklady a neznámý základ jsou viditelné.

## Význam souhrnů

Existující historie mají limit100 a některé filtry. Počet načtených záznamů
není celkový počet projektových úloh, agentů ani globální počet čekajících změn.
Souhrn uvádí rozsah, neodvozuje nové autoritativní stavy.

Návrh s jiným rodičem než aktuálním přijatým plánem se označí jako zastaralý
a nabídne kontrolu/převod. Známé nahrazené návrhy se neprezentují jako nové
nezávislé rozhodnutí. Nenahrané detaily se nevydávají za prokázaný dopad.

Loading, chyba, prázdná historie a skutečná nula jsou odlišné. Neúplná odpověď,
rozpor přijatých hlav nebo neúspěšná obnova ponechá viditelné omezení důvěry.
Stav běhu je označený časem načtení; expirace lokálně zneplatní aktivní značku.
Pokud model neobsahuje úplnou historii, rozhraní to uvede.

## Detail a akce

Každá akce otevře příslušný existující dílek: přesný rozdíl návrhu, konkrétní
execution a výsledky, důkazy PR, pravidla nebo historii. Stav a ukládání nadále
vlastní rodič; přehled neimplementuje druhý changeset či execution protokol.
Detail má čitelný nadpis, návrat/zavření a přesnou vazbu na vybraný záznam.
Modal/drawer má vpravo nahoře ✕, Escape a vrácení focusu. Změna projektu/prostoru
zavře detail a zneplatní navazující potvrzení. Neznámý nebo smazaný záznam se
označí, nesmí otevřít jiný návrh pod původním názvem.

Přijetí návrhu i změna pravidel zachovávají výslovné potvrzení, původní CAS,
bezpečný replay a zákaz automatického opakování mutací. Přehled nemění oprávnění
člověka/agenta. Historie a legacy dashboard zůstávají dostupné v detailu.

## Rozhraní pro agenty

Stejné API slouží UI a agentům: načíst kontext → navrhnout změnu → člověk
přijme → claim neměnného zadání → heartbeat → reported výsledek. Příklady uvádějí
scope a očekávané revize, nikdy tokeny. Chybějící baseline, zastaralý kontext,
vyčerpaný budget a vypršelá autorita jsou explicitní překážky, ne pobídka obejít
protokol. Agent může zapisovat návrh/výsledek, nemůže sám přijmout plán.

## Ověření

Přehled používá vlastní feature složku a BEM styly. Pure projekce mají testy
pro neúplná/chybová data, zastaralé návrhy, omezenou historii a smíšené revize.
Browser prokáže otevření přesné položky, zavření ✕/Escape, změnu scope,
prázdný a naplněný stav. Screenshoty desktopu a úzkého viewportu potvrzují
čitelnost; samotný vzhled neprokazuje backendové operace.
