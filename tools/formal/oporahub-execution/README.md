# Ohraničený model autority vykonávání

TLA+ model plánovaného protokolu OporaHubu. **Není důkazem správnosti Pythonu,
SQLite ani Office.** Každý přechod předpokládá jednu atomickou serverovou transakci.
Rollback, konkurence databázových spojení, legacy zápisy a ukončení workerů vyžadují
samostatné implementační testy.

Model zahrnuje claim, heartbeat, expiraci, nové převzetí, release, lidské vynucené
uvolnění, změnu přijaté revize i kontextu, nový výsledek a přesnou/konfliktní reprízu.
Receipt je nahlášený výsledek, nikoli ověření implementace nebo dokončení karty.

## Rozsah a předpoklady

Jedna karta, dva vlastníci, dvě epochy, dva claim request IDs, jeden result request ID
na execution a dva payloady. Serverový čas je0..2, TTL1 nebo2; revize i kontext se
mohou nezávisle změnit z0 na1. Žádné ořezávající state constraints ani simulace.
Hranice času/epoch je konečná, proto je vypnuté hlášení deadlocku; liveness ani
fairness se nedokazují. Autorita hodin se předpokládá, čas se nevrací.

Claim IDs jsou v modelu globální pro kartu; implementace je odděluje také podle
identity vlastníka a scope. Token je abstrakce schopnosti execution+owner+epoch,
nikoli kryptografický důkaz ani důkaz totožnosti osoby. Způsobilost zadání pro claim
je předpoklad; porovnání všech přijatých karet a legacy enrollment zde modelované
nejsou. Chybně autorizované požadavky jsou odmítnuté přechody bez změny stavu.

## Kontroly

- `MonotonicEpoch`: epoch nikdy neklesá.
- `OneActiveOwner`: nejvýše jeden běh má platnou autoritu.
- `NoUnauthorizedReceipt`: svědectví při vytvoření receipt má správnou epochu,
  sdílený lease, vlastníka, nevypršelý čas a shodnou revizi/kontext.
- `OneReceiptPerExecution`: druhý nový receipt po dokončení nevznikne.
- `Idempotency`: přesná repríza ani kolize requestId nemění počet receiptů;
  přechody současně zachovávají běhy, požadavky a receipty.
- `TypeOK`: konečné typy a maximální počet receiptů.

Negativní `NoFence.cfg` vypíná pouze společnou kontrolu epochy a identity lease,
zachovává všechna pozitivní invarianta i kontroly vlastníka, času a kontextu.
TLC odhalí dva oprávněné běhy po claim→force release→nový claim.
`NoEpochReceipt.cfg` nad stejným mutantem sleduje konkrétně následný opožděný
výsledek staré epochy. Jde o doplňkovou diagnostickou stopu, nikoli oslabení
pozitivního běhu. Runner ověřuje konkrétní název porušeného invariantu, nejen exit.

## Reprodukce a původ nástroje

Oficiální [TLA+ zdroj](https://github.com/tlaplus/tlaplus) a
[release v1.7.4](https://github.com/tlaplus/tlaplus/releases/tag/v1.7.4).
Použitý [tla2tools.jar](https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar)
identifikuje TLC2.19, 08 August2024, rev5a47802. Veřejný SHA1
`bee4a54f3ee3d4afc347c3240ec2d9e93b075104` souhlasí; release neposkytuje SHA256
ani samostatně ověřený podpis. Lokální SHA256 v `result.json` je reprodukční pin.
Model vychází z [Lamportova Specifying Systems](https://lamport.azurewebsites.net/tla/book-02-08-08.pdf).

Jar patří do externí cache, nikdy do repozitáře. Java21; jeden worker, heap768MiB:

```powershell
./Run-Checks.ps1 -Jar C:/external-cache/tla2tools-1.7.4.jar
```

Výstupy a TLC stavy jdou do nové dočasné složky (`-OutputDirectory` ji může změnit).
`-Mode negative` nebo `stale-negative` spustí jednotlivý mutation check.
Kladný běh musí vyčerpat frontu a skončit bez chyby; negativní musí vrátit exit12
se správným invariantem. `result.json` obsahuje dokončený běh a otisky artefaktů.
Původní širší průzkumný běh byl přerušen; není započítán jako úspěšné ověření.

## Vazba na implementační testy

Převést označené TLC přechody na API volání a po každém kroku porovnat epochu,
lease, stav execution, immutable assignment a receipt ID/počet. Hodiny injektovat.
Základní negativní sekvence: claim A → lidský force release → claim B → opožděný
result A musí skončit409, bez receipt. Přesná repríza úspěšného výsledku i po expiraci
musí vrátit původní receipt, změněný payload409. Po změně revize nebo relevantního
kontextu heartbeat/nový result409. Starý release nesmí uvolnit nového vlastníka.
Doplnit konkurenční claim, chybu/rollback mezi zápisy, legacy bypassy a Office
terminaci workeru; tyto vlastnosti z abstraktního modelu automaticky neplynou.

Otisky logů v `result.json` odkazují na lokálně ponechané soubory v dočasné složce,
nejsou přibalené do repozitáře. `.gitattributes` zachovává přesné ověřené bajty modelu
a konfigurací i při checkoutu na Windows. Historický běh použil fingerprint38 a
seed z `result.json`; runner používá pevné fp0/seed1. Pořadí průchodu a generované
statistiky se mohou lišit, definovaný konečný prostor a kontrolované vlastnosti jsou stejné.
