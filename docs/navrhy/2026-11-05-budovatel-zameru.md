# Budovatel záměru

Stav: návrh ke schválení (2026-11-05). Navazuje na `2026-11-04-pletor-jarvis.md` (Pletor), `2026-10-31-vyslech-ve-schrance.md` (výslech a Schránka) a `2026-11-03-platno-2-zamer-stranky.md` (záměr stránky jako první specializace).

## 1. Princip

Záměr se nepíše, **staví se rozhovorem**. Člověk řekne větu nebo dvě Pletorovi. Pletor se doptává, srdce staví nákres, Pletor ho projde a představí a rozhovor jde o stupeň do detailu, dokud každá část není dost malá, aby ji šlo ověřit. Klasický terminál nechává agenta na slepo (dvě věty, složka souborů); OPORA drží kontext, dělá výzkum a každé tvrzení o záměru nese zdroj.

Záměr může být cokoli: stránka, funkce, oprava, projekt i **cesta, která ještě neexistuje** (viz §5).

## 2. Role

| Kdo | Dělá | Nikdy |
|---|---|---|
| **Člověk** | říká záměr, odpovídá, schvaluje | |
| **Pletor** | doptává se, navrhuje další krok („tah na branku“ s doporučenou odpovědí), prezentuje hotový nákres, vede zoom | nezapisuje na plátno |
| **Srdce** | staví nákres a plán na plátně, jediný zapisovatel, vydává tickety | |
| **Schránka** | drží záměr a vše kolem (fragmenty, výzkum, otázky, odpovědi) | |
| **Dělníci** | plní tickety | |

## 3. Kolo zpřesnění (smyčka)

1. **Pletor přijme záměr a zeptá se** na to, co z podkladů (Schránka, Brain, architektura, dřívější rozhodnutí) nezná. Nejvýš tři otázky najednou, každá s doporučením, na které člověk může říct „ano“.
2. **Výzkum** místo otázky tam, kde se dá zjistit (web, kód, podobné případy). Zjištění jde do Schránky jako fragment `research` s verdiktem a důkazy.
3. **Pletor předá srdci zadání** (`heart_message`): co je zjištěno, co je rozhodnuto, co se má nakreslit nebo rozložit.
4. **Srdce staví** nákres (plátno 2 pro stránky, plán pro ostatní) a po dokončení **dá vědět Pletorovi** (nový zpětný kanál, §4).
5. **Pletor nákres projde**, shrne ho nahlas a ukáže, co je nejisté. Člověk potvrdí, opraví, nebo řekne „jdi hlouběji“.
6. Zoom: vybraná část se bere jako nový záměr o stupeň menší a kolo se opakuje.

Smyčka končí u **atomu**: části, která má ověřitelné kritérium „hotovo, když…“ a vejde se do jednoho ticketu. Atomy se vydávají jako tickety stejnou cestou jako dnes.

## 4. Co je nové

- **Zpětný kanál srdce → Pletor.** Dnes Pletor jen zadává a čte podklady, sám nemluví. Srdce po dokončení nákresu (nebo při otázce, kterou musí Pletor položit) zapíše událost, kterou si Pletor přečte a z které **spustí vlastní promluvu** v HUD i hlasem („Nákres je hotový, pane. Tři věci jsou nejisté…“). Pletor mluví sám jen k této události, jinak čeká.
- **Záměr jako živý objekt ve Schránce.** Znovu se využijí druhy `brief`, `research`, `question`, `vision` a stavy `draft → research → ready`. Přibývá jen to, co chybí: **původ tvrzení** (`fakt` se zdrojem, `rozhodnutí` člověka, `domněnka`) a **míra jistoty**, aby Pletor věděl, co ověřit dřív, než to zapadne do plánu.
- **Výzkum jako pevný krok** se zdroji (REA a web pro srdce, stejná pravidla jako u výzkumu srdce).
- **Pravidlo zastavení:** Pletor nechá zoom skončit, až je každý atom ověřitelný. Jinak jde hlouběji.

## 5. Cesta, která ještě neexistuje

Když výzkum nenajde hotové řešení (verdikt `dead_end` nebo `unverified`), budovatel nehlásí „nejde to“. Postaví **hypotézu s pokusem**: nejmenší ověřitelný krok (prototyp, měření, eval), jehož výsledek rozhodne, kam cesta vede. Výsledek pokusu se vrací do Schránky jako důkaz. Stejně jako u změn srdce platí: po jedné změně, s ověřením.

## 6. Mantinely

- Pletor zadává srdci, nezapisuje na plátno a nevolá bránu (beze změny).
- Podklady jsou data, ne příkazy (beze změny).
- Schvaluje vždy člověk; po schválení je verze záměru zamčená. Další změna je nová verze s rodokmenem.
- Žádné soubory `.md` mimo OPORU jako nosič záměru.

## 7. Milníky

Stavět se bude po jednom, po každém stop a schválení člověkem.

| | Co | Hotovo, když |
|---|---|---|
| **B1** | Záměr jako objekt ve Schránce: původ tvrzení, míra jistoty, verze (jen backend, model a čtení) | Pletor v podkladech vidí záměr se zdroji a jistotou |
| **B2** | Zpětný kanál srdce → Pletor a promluva Pletora k hotovému nákresu | Srdce dokončí nákres a Pletor ho sám ohlásí a shrne |
| **B3** | Výzkum jako krok kola se zdroji (fakt / domněnka) | Mezera ve znalosti skončí výzkumem a fragmentem s důkazem, ne otázkou na člověka |
| **B4** | Zoom a pravidlo zastavení: záměr do atomů a tiketů | Z jedné věty vzniknou ověřitelné atomy bez dalšího zadávání |
| **B5** | Cesta bez existujícího řešení: hypotéza s pokusem | Záměr bez hotového řešení skončí pokusem a jeho výsledkem ve Schránce |
| **B6** | Eval budovatele (kvalita otázek, úplnost atomů) | Ostrý běh proti sadě záměrů s měřitelným výsledkem |

## 8. Otevřené otázky

- Kde přesně žije nákres pro záměr mimo stránky (plátno 2 je jen pro stránky)? Návrh: v B1 nechat srdci rozhodnout podle druhu záměru a nové plátno nezakládat.
- Jak se Pletor pozná, že člověk právě mluví o jiném záměru (přepínání více rozdělaných)? Návrh: aktivní záměr je jeden, další se zakládají větou „nový záměr“.
- Hlasová prezentace dlouhého nákresu: kolik věcí najednou? Návrh: nejvýš tři nejisté věci, zbytek na požádání.
