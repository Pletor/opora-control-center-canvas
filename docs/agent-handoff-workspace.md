# Pracovní prostor agentů — obsah sekcí a předání scénářů

Navazuje na `docs/karta-pro-agenty.md`, sekce Pracovní prostor agenta a Fraktální předávka. Níže je popsané použití dnešní v1 s pěti klíči API v **Text → Agenti**, nikoli konečná podoba komunikace mezi agenty.

**Rozšířený plán:** [Pracovní prostor a komunikace mezi agenty](../.hermes/plans/2026-09-16_092217-agent-communication-workspace.md). Na základě upřesnění uživatele doplňuje skutečné sekce pro odpovědnost, vstupy, příchozí/odchozí zprávy, otázky a rozhodnutí, důkazy, obnovu a audit. Definuje adresaci, potvrzení přesné verze, idempotenci a ochranu souběžného vlastnictví. Je to návrh změn API a UI; nové funkce zatím nejsou implementované. Původních pět polí zůstává kompatibilní pracovní pamětí, nikoli náhradou komunikačního protokolu.

## Prověřené předchozí plány

V projektu OPORA Control Center — vývoj aplikace:
- `7945a4a2-1c3c-4814-ab37-1cfbc853203f` — Pracovní prostor agentů: pět sekcí per karta, CAS, přenos do node-brief.
- `67d57a21-a7d8-4a94-9425-0fb9e90ea61a` — návaznost pravého navbaru; odkazuje na první kartu.
- `7163feb0-4e49-44dc-a258-851cc0af2ba8` — náhled balíčku v záložce Agenti; čte existující prostor, nic nespouští.

Původní texty zůstávají zachované. Pracovní scénáře vznikají odděleně pod Pamětí agentů.

## Pět sekcí

### Rámec a směr (`frame`)
- Smysl a cíl této práce, odkaz na skutečné zadání karty.
- Přesný projekt/workspace/node, role a hranice zápisu.
- Kritéria výsledku a očekávané chování; žádná záměna plánu za důkaz.
- Odkaz na autoritativní kontrakt. Jde o paměť práce, ne nové nadřazené instrukce.

### Postup (`log`)
- Čas, hypotéza, provedená akce, skutečná odezva.
- Rozlišit API klienta, skutečný model a ruční/automatické ovládání UI.
- Každý pokus a zotavení zaznamenat; neúspěšný pokus nesmí zmizet.
- Přiložit cestu k syrovému výsledku, revize a identitu běhu.

### Co se nepovedlo (`failures`)
- Reprodukční kroky a vstup, očekávaný versus skutečný výsledek.
- Dopad a přesné omezení důkazu; blokaci neoznačit za chybu produktu.
- Co nefungovalo a nemá se bez změny opakovat.
- Stav FAIL / BLOCKED / UNVERIFIED s důvodem, ne prázdné optimistické shrnutí.

### Úspěšné opravy (`fixes`)
- Příčina, minimální změna a dotčené soubory.
- Commit, pokud skutečně existuje; jinak výslovně pracovní kopie.
- Oddělit opravu kódu, nasazení a ověření chování.
- Odkazy na důkazy, zbývající rizika. Pro čistě ověřovací scénář napsat, že se kód neměnil.

### Předávka (`handoff`)
Musí být samostatně srozumitelná i bez logu:

```text
STAV: PENDING | RUNNING | PASS | FAIL | BLOCKED | UNVERIFIED
CÍL A ROZSAH: konkrétní karta, projekt, workspace, povolené změny
DOLOŽENO: pouze reálně dokončené a zpětně přečtené výsledky
NEOVĚŘENO / BLOKACE: přesný chybějící důkaz nebo závislost
DALŠÍ KROK: jedna konkrétní akce a podmínka jejího provedení
HRANICE: co další agent nesmí měnit; žádný automatický restart či rozpočet navíc
DŮKAZY: přesné soubory / URL / revize / session ID
NÁVAZNOST: skutečný rodič, předchůdce, následník; nezaměňovat je
```

Rodič, potomci a sousedé v oblasti dostávají jen `frame` a `handoff`. Kritické blokace, výsledek a další krok proto nikdy nesmějí zůstat pouze v `log` nebo `failures`.

## Ukládání

- Částečný POST `agent-workspace`, vždy s právě načtenou `expectedRevision`; po zápisu GET stejného cíle.
- Při konfliktu nezvyšovat revizi nad starou kopií. Zachovat rozepsaný obsah a znovu posoudit aktuální stav.
- Sekce nejvýše 12 000 znaků. Syrové rozsáhlé důkazy uložit do lokálního artefaktu, v prostoru nechat shrnutí a odkaz; tiše nezkracovat.
- Odkazy `opora://agent-workspace/<nodeId>#<sekce>` označují sekci. Samotná existence odkazu není důkaz implementované navigace v prohlížeči.
- Scénáře mění jen vlastní nové karty; existující uživatelské karty a jiné projekty se zachovávají.

## Co uživatel vidí v Text → Agenti

Podzáložka **Agenti** není dokument ke čtení, ale pracovní plocha přes celou šířku
(`frontend/editor/node-detail/agent-workspace/segments/`). Sloupec 860 px, který drží text Uživatele
čitelný, tady nesvazuje nic (`text-workspace--agents`); podzáložka Uživatel zůstává beze změny.

**Vlevo lišta karet** (`AgentCardRail`): vrstva, ve které člověk stojí, a pod ní její děti. Klik na
řádek přepne, čí prostor se kreslí vpravo; „Zanořit“ u dítěte dělá totéž co v dokumentu – přejde
o patro níž. Napravo stojí vždy **právě jeden** pracovní prostor (`AgentWorkspace` s `key={nodeId}`),
takže vrstva s deseti dětmi nedělá deset dotazů a uzavřená karta (`done.confirmed`) je dál jen ke čtení.

**Vpravo devět pojmenovaných segmentů** v pevném pořadí. Každý má titulek, jednu větu „k čemu to je a
kdo sem píše“, kotvu `#agent-seg-<nodeId>-<segment>` a přepínač Sbalit/Rozbalit; sbalený segment
nezmizí, jen schová tělo, takže se plocha pod rukama nehýbe:

1. **Přehled** (`AgentOverview`) – pás přes celou šířku, jediný segment, který se nesbaluje. Cesta
   karty a tři oddělené stavy: Práce (kdo psal naposled, kolik z pěti polí je vyplněno), Komunikace
   (Bez potvrzení / K upřesnění / Otevřené otázky z briefu), Ověření (cíl a definice hotovo přítomné
   či chybějící, počet mezer). Pod tím Další krok z `orientation.nextAction` (označený jako
   doporučení, ne přijatý úkol), bezpečnostní věta z `orientation.safety` a přesný důvod zámku:
   uzavřená karta, nebo main jen ke čtení. Brief se načítá jednou a sdílí s orientací.
   Počty a dlaždice jsou zároveň rozcestník: Bez potvrzení / K upřesnění / Otevřené otázky vedou do
   Komunikace, Mezery do Startu pro agenta, Práce do Rámce a směru – a cílový segment se cestou sám
   rozbalí. V pásu stojí i **Rozbalit vše / Sbalit vše** pro celou plochu.
2. **Start pro agenta** (`AgentOrientation`) a **Komunikace** (`AgentCommunication`) jako dvě poloviny
   pod přehledem. Start: karty Cíl / Co přečíst / Co chybí / Další krok, hledání v načteném kontextu,
   kopie celého JSON. Komunikace: jeden seznam vláken, nejnovější kořen nahoře, odpovědi odsazené pod
   kořenem. Každá zpráva nese směr, typ, stav (Uloženo, nepřevzato / Převzato / Odmítnuto / Vyžaduje
   upřesnění), deklarovaného autora s „identita neověřena“ a zkrácený digest; zpráva nahrazená opravou
   má štítek „Nahrazeno opravou“. Vlákno, které čeká na převzetí nebo odpověď, má zvýrazněnou hranu a
   počítá se do hlavičky „N nevyřízené“. Převzít / Odmítnout / Potřebuji upřesnění se nabízí jen
   u příchozí zprávy bez potvrzení a nikdy automaticky.
3. **Paměť role** (`AgentMemoryPanel`) přes celý řádek pod dvojicí. Pět polí paměti níž patří jedné
   kartě; tenhle segment drží zkušenost *kompetence*, která kartu přežije (`docs/pamet-agentu.md`).
   Napoprvé je zavřený, protože sahá na cizí službu (OpenViking). Po otevření se přečte jen přepínač
   aplikace a knihovna rolí: vypnutá paměť řekne „Paměť rolí je vypnutá. Zapni ji v Nastavení →
   Napojení.“, nedostupný server ukáže důvod a adresu. Nahoře stojí **role karty** (`agentRole`) jako
   výběr z `library/agent-roles.json`; karta bez role to přizná („Karta nemá roli“) a paměť se u ní
   nečte ani nezapisuje. Roli ukládá deska obyčejnou mutací stavu Desktop v3, ne zvláštní cestou.
   Pod tím je dotaz a tlačítko **Vybavit** – prázdný dotaz se ptá cílem karty. Výsledky jsou
   rozdělené podle původu: „Vlastní zkušenost“ (`self`), „Tento projekt“ (`project`) a „Zapůjčeno od
   <role>“ (`lent:<role>`), každá položka s adresou a s podobností na dvě desetiny; skóre je blízkost
   dotazu, ne důvěra ani ověřený fakt. Dokud si člověk nevybavil sám, ukazuje se paměť, kterou už
   nese balíček karty (`context.roleMemory`), označená „zatím z briefu karty“. Úplně dole jsou dvě
   vědomé akce: **Zapamatovat** (poznámka / poučení / rozhodnutí, text do 12 000 znaků, samostatné
   tlačítko – u uzavřené karty se formulář vůbec nekreslí) a **Zapůjčit od role…**, jejíž výsledek
   přijde do vlastní skupiny označené jako půjčka. Nic z toho se nespustí samo: aplikace tu nezapisuje
   bez potvrzení člověka a žádný model nespouští. Přepínač paměti je v Nastavení → Connectors, kde
   OpenViking ukazuje živý stav z `GET /api/memory/status` a tlačítko volá `POST /api/memory/settings`.
4. **Pět polí paměti karty** – Rámec a směr, Postup, Co se nepovedlo, Úspěšné opravy, Předávka – jako pět
   stejně širokých sloupců vedle sebe, každý s indikátorem „prázdné / N znaků“ a tlačítkem
   „Kopírovat odkaz“ (`opora://agent-workspace/<nodeId>#<sekce>`). Popisek každého pole přiznává, že
   jde o poznámky modelu k této kartě, ne o zadání. Text se ukládá při opuštění pole (blur).

**Co je rozbalené, je vzhled, ne obsah karty**: ukládá se jednou pro celou aplikaci pod klíčem
`opora:agent-segments:v1` (`{ open: { <segment>: boolean } }`), nikdy s klíčem projektu. Napoprvé
jsou otevřené Přehled, Start pro agenta a Komunikace a ta pole paměti karty, která už něco nesou;
Paměť role zůstává zavřená, dokud ji člověk neotevře. Jakmile si své nastaví, platí jeho volba.
Přehled zůstane otevřený vždy.

**Responzivně**: od 1100 px lišta karet 260 px vlevo a segmenty vpravo (Přehled přes celou šířku,
Start a Komunikace po polovině, Paměť role přes celý řádek pod nimi, pět polí paměti karty v jedné
řadě). Pod 1100 px se lišta přesune nad plochu a segmenty se skládají do sloupců po 280 px;
pod 720 px zůstane jeden sloupec.

Pravidla umístění a skládání: `docs/pravidla-struktury.md`, kontrakt karty: `docs/karta-pro-agenty.md`.
