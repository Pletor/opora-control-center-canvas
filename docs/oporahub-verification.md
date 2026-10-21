# Formální ověřování: vstupy, tvrzení a výsledky

OporaHub eviduje formální kontrolu jako neměnný požadavek a nejvýše jeden
neměnný výsledek. Požadavek zachytí skutečnou přijatou revizi, digest zadání,
kartu, execution ID a epochu ze serveru. Nahlášený commit, model a výstup jsou
samostatné podklady; nejsou důkazem, že danému commitu odpovídá implementace.

Tato etapa připravuje společnou evidenci pro TLA+/TLC a Lean. Žádný import
neobdrží důvěru nezávislého ověřovače. `trust` má vždy hodnotu `agent-reported`
a `independentlyVerified` je vždy `false`, včetně výsledku `passed`. Politika
review, dokončení karty ani merge se tím nemění. Úspěch TLC znamená kontrolu
uvedeného konečného modelu; úspěšné sestavení Lean samo není kontrolou důkazu.

## Protokol a oprávnění

Základ je `/api/oporahub/verifications`. Zápisy používají existující execution
token; token nikdy není v historii ani v uloženém požadavku. Server při prvním
zápisu i bezprostředně před uložením kontroluje epochu, lease, neměnné zadání
a pevný konec běhu. Vytvoření kontroly neuvolňuje kartu ani nezakládá druhý lease.

- `POST /requests`: `{project, workspace, executionId, token, epoch, requestId,
  verification}`. Totožná identita i obsah vrací původní záznam; jiný obsah
  pod stejnou identitou je konflikt. `verification` obsahuje přesně `tool`,
  `source`, `claims`, `assumptions`, `configuration`, `artifacts`.
- `tool`: `{name: "tlc" | "lean", version, distributionSha256}`. `source`:
  `{repository, commitSha}`; repository je `owner/name`, SHA je 40 malých hex
  znaků. Jde o tvrzení předkladatele, nikoli potvrzenou identitu GitHubu.
- `claims`: 1–32 záznamů `{id, kind, statement}`, kde kind je `invariant`,
  `temporal-property` nebo `theorem`; ID jsou unikátní. U Lean jsou přípustná
  jen theorem, u TLC invariant a temporal-property. Server doplní digest tvrzení.
  `assumptions` je nejvýše 32 neprázdných textů, `configuration` je omezený JSON
  s uvedením konečných mezí, fairness, axiomů a režimu kontroly podle nástroje.
- Každý vstupní artefakt je `{path, role, sha256, dataBase64}`. Server ověří
  přesné původní bajty a velikost, sestaví seřazený manifest a jeho SHA256.
  Role jsou `model`, `configuration`, `dependency`, `proof`, `source`, `lockfile`.
  Jména jsou relativní POSIX cesty bez traversal, zpětných lomítek a prázdných
  segmentů; žádné symlinky se nepřenášejí. Nejvýše 32 souborů na zprávu.
  Vstupy nejsou prázdné: TLC vyžaduje model i konfiguraci, Lean proof nebo source.
  Úplnost importů a závislostí zůstává tvrzením předkladatele.
- `POST /{id}/report`: `{project, workspace, token, epoch, requestId, report}`.
  `report` obsahuje přesně `outcome`, `checkedClaims`, `summary`, `artifacts`.
  Outcome je `passed`, `counterexample`, `failed`, `inconclusive` nebo `cancelled`.
  CheckedClaims jsou unikátní ID z požadavku; passed vyžaduje všechna tvrzení.
  Passed vyžaduje alespoň jeden výstupní soubor, counterexample soubor této role.
  Výstupní role jsou `stdout`, `stderr`, `counterexample`, `proof`, `run-metadata`.
  Místní TLC export přikládá také metadata běhu: skutečný začátek a konec,
  exit code, důvod ukončení, nastavený časový limit a otisky runneru. Jde stále
  o nahlášená metadata, nikoli autentizovaný původ nezávislého ověřovače.
  Totožné opakování vrací původní výsledek i po skončení běhu. Konflikt odmítne.
  Nový výsledek po ztrátě oprávnění nepřijme. Časy přijetí určuje server.
- `GET ?project=…&workspace=…&nodeId=…` vrací nejvýše 100 posledních požadavků
  s výsledky; nodeId je nepovinné. `GET /{id}?project=…&workspace=…` vrací přesný
  požadavek a výsledek i po odstranění karty nebo archivaci prostoru.
- `GET /{id}/artifacts/{sha256}?project=…&workspace=…` zpřístupní pouze bajty
  uvedené v daném manifestu. Odpověď je příloha, `application/octet-stream`,
  `nosniff`, CSP sandbox. HTML ani SVG se nespouští.

`requestId` má stejný formát jako execution request ID. Neznámá pole, duplicitní
cesty, neplatné base64/SHA, nekonečná čísla a neomezené vnoření JSON se odmítají.
Text je nejvýše 4 000 znaků, konfigurace nejvýše 16 KiB a 8 úrovní. Jeden soubor
má nejvýše 2 MiB, vstupy a výstupy jednoho požadavku dohromady nejvýše 8 MiB,
projekt nejvýše 64 MiB unikátních bajtů. HTTP JSON tělo má limit 12 MiB.

## Uložení, historie a zobrazení

Bajty jsou v projektovém SQLite jako SHA256 adresované BLOB, odděleně od JSON
metadat. Vložení souborů a požadavku či výsledku je jedna transakce. Kvóty se
počítají v téže transakci; neúspěšný zápis nezanechá částečný úspěch. Čtení znovu
ověřuje hash a velikost. Chybějící či změněné bajty jsou nedostupný podklad,
nikoli zelené ověření. Zálohování celé projektové DB zahrnuje historii i bajty;
destruktivní obnova starší DB nesmí novou evidenci odstranit.

Detail výsledku ukazuje skutečnou revizi a execution, nahlášený commit, nástroj,
tvrzení, předpoklady, konfiguraci a soubory ke stažení. Důvěra je viditelná
vedle výsledku. Změněná přijatá revize označí historii jako zastaralou; tato
etapa vůbec neuděluje použitelnost pro automatické rozhodnutí o správnosti.

## Oddělený ověřovač a zbývající práce

Agent nejprve převezme běžné execution oprávnění. [Místní TLC export](../tools/formal/oporahub-execution/README.md)
vytvoří `verification.json` a `report.json` bez tokenu. Klient obalí první soubor
scope, execution ID, tokenem, epochou a stabilním requestId a odešle jej na
`/requests`. Druhý odešle s credentials na `/{id}/report`; potom může obvyklým
execution resultem odkázat uložená ID. Export sám API nevolá a heartbeat běhu
zůstává povinností vykonavatele. Po ztrátě oprávnění lze jen přesně opakovat
již uložený zápis, nikoli přidat nový výsledek.

Spouštění patří do Office/CI. Import neprovádí příkaz, neinstaluje nástroj,
nenačítá URL a nesvěřuje agentovi volbu důvěry. Místní TLC profil musí zachovat
přesné vstupy, verzi a hash nástroje, konečné meze, výstup i důvod ukončení.
Timeout, nedokončený průchod, simulace nebo useknutý potřebný výstup nemají
výsledek passed. Kontrola negativních mutantů dokládá citlivost modelu,
nikoli správnost Pythonu nebo TypeScriptu.

Důvěryhodný Lean adaptér zatím není k dispozici. Vyžaduje izolované sestavení,
nezávisle zadané očekávané tvrzení, kontrolu proof termů a tranzitivních axiomů;
`sorryAx` a neschválené axiomy se nesmějí přijmout. Samotný log autora ani
`lake build` tuto podmínku nesplňují. Viz [validace důkazů Lean](https://lean-lang.org/doc/reference/latest/ValidatingProofs/).

Nezávislé ověřování vyžaduje zvlášť implementovaný izolovaný runner, vynucené
limity procesového stromu a ověřený původ výsledku. Vypnutý Docker nebo chybějící
Lean se zobrazí jako nedostupná schopnost. Model, důkaz a test shody skutečné
implementace jsou tři odlišné typy důkazů.
