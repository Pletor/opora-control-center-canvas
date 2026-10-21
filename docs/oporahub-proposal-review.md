# Review konkrétního návrhu — kontrakt etapy 3b

Etapa je implementována a ověřena v backendu i společném detailu návrhů;
konkrétní důkazy a známé dluhy jsou uvedeny níže. Navazuje na
neměnné návrhy zadání, grafu a [obsahu](oporahub-content-changes.md). Dosavadní
[GitHub review policy](oporahub-review-policy-contract.md) kontroluje PR a SHA;
neopravňuje přijmout jiný návrh plánu.

## Rozhodnutí a meze

Připomínka patří přesnému projektu, workspace, druhu a neměnnému ID návrhu.
Rebase vytvoří nové ID: původní diskuse zůstane dostupná, ale žádné potvrzení
se automaticky nepřenese. Přijatý plán stále mění jen člověk stejnou operací
přijetí; review nevytváří další způsob zápisu do grafu ani zadání.
API rozlišuje `spec`, `graph-addition`, `graph-change` a `content`; nesoulad druhu
se skutečně uloženým návrhem odmítne.

Lokální identita `human` nedokládá dvě různé osoby. Tato etapa poskytuje
vypořádání nálezů a výslovné lidské potvrzení rizika; nepočítá jména
agentů nebo lokální session jako nezávislé lidské hlasy. Nahlášený nález agenta
je označen původem a zůstává tvrzením autora.

## Data a API

Samostatný modul uchová append-only, hashované a scope-ověřené události review
a revize acceptance policy s CAS hlavou. Projektové schéma je vytvoří před
zapnutím context journalu. Obnova zkontroluje odkazy a integritu; historie se
nepřepisuje ani nemaže. Všechny vstupy, počty a bajty mají pevné limity.
Policy má nejvýše32KiB a256 revizí na scope, událost64KiB a2048 událostí na
návrh, zpráva8000 znaků. Společná projektová kvóta neměnných review záznamů
je64MiB; vyčerpání nic nezkrátí ani nesmaže.
Acceptance receipt má nejvýše 32 KiB a patří do stejné projektové kvóty.
Klíč idempotence má nejvýše 128 znaků. JSON má omezenou hloubku; duplicitní klíče,
neplatné typy, scope a hash se odmítnou. Žádné mazání nebo skryté zkrácení historie.

Read endpoint pro přesný návrh vrátí serverem vypočtené riziko a jeho důvody,
aktuální policy, události, otevřené nálezy a podmínky přijetí. Agent i člověk
mohou přidat komentář nebo nález; jen člověk může označit nález jako vyřešený
nebo jej výslovně přijmout s odůvodněním. Změna stavu odkazuje konkrétní nález
a očekávanou hlavu diskuse. Přijetí rizika člověkem je zvláštní neměnná událost
vázaná na ID návrhu, rodiče, policy a přesnou hlavu review.

Nový komentář/nález, jeho vypořádání nebo změna policy zneplatní staré potvrzení.
Opakovaný klientský request se stejným idempotency key nesmí přidat další událost;
stejný klíč s jiným obsahem je konflikt. Nejisté zápisy UI samo neopakuje.
Idempotentní replay porovnává také serverem určeného autora; ignoruje jen čas
vytvoření a odvozené ID. ACK ukládá úroveň rizika i digest jeho přesných důvodů.

## Riziko a atomické přijetí

Riziko klasifikuje server z uloženého návrhu, nikoli klient. Konzervativní třídy:

| Třída | Minimální důvody |
|---|---|
| běžné | Samostatný text, kresba nebo materiály bez změny řídicích polí |
| zvýšené | Zadání, přidání karet/vazeb, změna pravidel, akcí, bloků nebo příznaku stahování URL |
| kritické | Odstranění karet/vazeb, změna sdíleného kontextu architektury, první převzetí celého grafu/obsahu |

Policy aktivuje nebo mění pouze člověk. Určí třídy vyžadující výslovné potvrzení
a zda otevřené blokující nálezy brání přijetí. Výchozí absence/disabled policy
zachová dosavadní acceptance payloady a lidské přijetí. Přímý počáteční spec
baseline je při aktivní policy výslovná bootstrap výjimka jen pokud současně
neexistuje accepted head ani žádná historická přijatá revize daného scope.
Stejná transakce uloží neměnný bootstrap záznam navázaný na novou revizi a policy;
existující záznam nebo historie výjimku vylučuje i po smazání reference.
Nejde o schválení pozdějšího návrhu. UI ji musí takto označit.

Sdílený guard se provede uvnitř stávající BEGIN IMMEDIATE transakce všech čtyř
acceptorů, po ověření návrhu a preconditions a před native zápisy. Znovu načte
aktuální policy a review; stale potvrzení nebo otevřený blokující nález při
aktivním pravidle odmítne. Potvrzení a přesná policy musí být dohledatelné
z přijaté revize. Replay již přijatého návrhu vrací původní výsledek.

Stejné chování nyní platí také pro návrhy zadání: opakované lidské přijetí přesného
již přijatého ID vrátí původní revizi, i když mezitím přibylo review nebo se změnila
policy. Dva souběžné requesty stejného ID mají jeden native zápis a stejné ID výsledku.
Dva odlišné návrhy nad stejným rodičem dál soutěží přes CAS: uspěje jeden a druhý
musí být výslovně přenesen na novou hlavu. Replay nepřenáší souhlas na jiné ID.
Při aktivní policy stejná transakce uloží neměnný acceptance receipt navázaný
na přijatou revizi, policy, riziko a review/ACK hlavu. Při absent/disabled policy
guard ani seal žádný receipt nepíše; review kvóta tak nemění legacy přijetí.
Absence receipt není potvrzení provedeného review.

## Rozhraní a dokončení

Na přehledu otevřete **Pravidla přijetí plánů**; tato policy neřídí GitHub PR.
**Review návrhu** je uvnitř dosavadního detailu zadání, přidání grafu, změny grafu
i obsahu. Zobrazuje důvody nepřijetí, původ nálezů, aktuální policy/review hlavu,
historii a přesný doklad přijetí, pokud existuje. Chybějící model nebo API znamená
nedoložené podklady, nikoli splněné review. Světlý/tmavý motiv používá stejné
theme proměnné; drawer zachovává ✕, Esc a návrat fokusu.

Stejný detail návrhu zobrazí riziko, diskusi, otevřené nálezy, jejich lidské
vypořádání a potvrzení. Přehled ukáže proč návrh čeká; všechna tlačítka používají
stejné API jako agenti. Scope/ID a pozdní odpovědi se oplocují stejně jako u
obsahových návrhů. Zavření zruší místní neodeslané potvrzení.

Dokončení vyžaduje API a skutečný browser průchod pro všechny druhy návrhů,
stale policy/review/rebase a souběžný nález vs acceptance, atomicitu/rollback,
agent/human oprávnění, replay, kvóty a obnovu. Nevyžaduje produkční zásah.

## API pro člověka i agenta

Základ je `/api/oporahub/proposal-reviews`. Všechny operace nesou `project` a
`workspace`; návrhové operace navíc `proposalKind` a přesné `proposalId` (40 hex).
Identitu stanoví middleware: agent používá `X-Opora-Actor: agent; name=<jméno>`,
prohlížeč získá lidskou session přes `GET /api/access/ui-session`. Pole `by` se
do requestu neposílá. Read-only scope vrací odpovídající vypnuté capabilities;
mutace readonly nebo neexistujícího pracovního prostoru se odmítnou.

| Operace | Přesné údaje |
|---|---|
| `GET /policy?project=…&workspace=…` | `policyHead`, `policy`, `acceptedHead`, `bootstrapException`, `readOnly`, `canConfigure` |
| `POST /policy` | `{project, workspace, expectedPolicyHead, enabled, rules}`; jen člověk |
| `POST /policy/disable` | `{project, workspace, expectedPolicyHead}`; jen člověk, nová disabled revize |
| `GET ?project=…&workspace=…&proposalKind=…&proposalId=…` | Riziko `{level,reasons,digest}`, policy/review hlavy, události, otevřené nálezy, aktuální ACK, blokující důvody, capabilities, přesná `acceptedRevision` a `receipt` nebo null |
| `POST /events` | `{project, workspace, proposalKind, proposalId, expectedReviewHead, idempotencyKey, body}`; jednoznačně popsaná událost níže |
| `GET /receipts/{acceptedRevision}?project=…&workspace=…` | `{receipt}`; přesný uložený doklad nebo null, nikdy odhad podle aktuální hlavy |

Policy se nastaví například takto; `expectedPolicyHead` je skutečná načtená hlava,
null jen při její absenci. Práh je `standard`, `elevated`, `critical` nebo `none`.

```json
{"project":"projekt","workspace":"draft","expectedPolicyHead":null,"enabled":true,"rules":{"requireAcknowledgementFrom":"elevated","blockOpenFindings":true}}
```

Agent i člověk mohou přidat komentář nebo nález nad načtenou hlavou diskuse:

```json
{"project":"projekt","workspace":"draft","proposalKind":"content","proposalId":"<přesné ID>","expectedReviewHead":null,"idempotencyKey":"<nový klíč explicitní akce>","body":{"type":"finding","message":"Ověřte dopad této změny.","anchor":"/changes/0/value","severity":"blocking"}}
```

`anchor` je existující RFC6901 cesta v neměnném návrhu, `""` označuje celý návrh.
`comment` má `message` a `anchor`; `finding` přidává `severity` z
`info|warning|blocking`. Jen člověk posílá `resolve` s
`{type, targetEventId, resolution: "resolved"|"accepted", reason}`. Odůvodnění je
povinné; cíl musí být otevřený nález téže diskuse. Jen člověk smí poslat ACK:

```json
{"project":"projekt","workspace":"draft","proposalKind":"content","proposalId":"<přesné ID>","expectedReviewHead":"<reviewHead>","idempotencyKey":"<nový klíč potvrzení>","body":{"type":"ack","policyId":"<policyHead>","riskDigest":"<risk.digest>","parentAcceptedHead":"<acceptedHead>"}}
```

Server ukládá třídu rizika i digest jeho důvodů a očekávanou review hlavu. Pro
první grafový plán mohou být obě přijaté hlavy null; jde o doložený prázdný základ,
nikoli chybějící kontext. Kritický graph proposal při aktivní policy přesto
vyžaduje standardní review/ACK. Odlišná spec bootstrap výjimka je popsána výše.
Native accept payloady zůstávají původní: guard znovu načte aktuální review ve
stejné transakci. `409` znamená konflikt nebo odmítnuté podmínky, `428` chybějící
identitu. Zápis UI automaticky neopakuje; shodný klíč i autor s původním obsahem
vrátí stejnou událost i po posunu hlavy, jiný obsah nebo autor je konflikt.

## Upgrade a kontinuita kontextu v2

Přidání nových review tabulek a triggerů změní DDL generaci již zařazené projektové
DB. Dřívější sparse coverage proto odmítne pokračovat, i když je nová policy
zatím nepřítomná. Historie, klíče, soukromé piny a staré doklady se zachovají;
v1 funguje při splnění svých podmínek. Automatická oprava/reset/re-enrollment
neexistují. Nesmí se přepsat fingerprint nebo smazat důkazy pro obnovení lease;
platí [stejné pravidlo změny schématu](oporahub-sparse-context.md) jako u obsahu.

## Důkazy etapy 3b

Celý frontend prošel: 226 souborů, 1 580 testů; TypeScript i produkční build
prošly. Backend/database běh skončil s 3 272 passed, 4 skipped a dvěma chybami:
známou baseline chybou Graphify (`test_map_refresh.py:219`) a starým očekáváním
409 při opakování již přijatého spec návrhu. Druhé očekávání bylo upraveno podle
výše popsaného kontraktu idempotence, bez další změny produkčního kódu.
Následná cílená sada má 28 passed; doplněná kontrola počtu SQL revizí má 3 passed.
Původní celý běh proto není vykazován jako zelený ani jako znovu provedený.
Samostatná integrace review měla 45 passed a test odlišných souběžných návrhů
ověřil jediného vítěze CAS. Nové moduly prošly scoped Ruff; globální starší dluh
statických kontrol zůstává beze změny a jejich limity nebyly zvýšeny.

Skutečný factory API a headless browser na syntetických datech ověřil všechny
čtyři druhy návrhů, lidské nastavení policy, agentův nález a odmítnutí agentova
resolve/ACK/policy/accept. Lidské vypořádání s důvodem obnoví stejný detail;
nový komentář nebo policy zneplatní ACK. Rebase vytvoří nové ID bez přenesených
událostí a potvrzení, přijetí uloží receipt vázaný na přesné ACK.
Po přijetí zadání se další práce obnoví běžným tlačítkem „Obnovit podklady“.
Regrese duplicitních formulářů po obnově je opravena unikátními React keys;
browser ověřil jediný formulář a potvrzovací oddíl bez reloadu stránky.
✕/Esc vrací fokus, mobilní šířka 390 px nepřetéká, světle/tmavý kontrast byl
14,61:1 / 11,88:1; nevznikly JS chyby ani varování duplicitních keys.
Nejde o test produkčních dat, skutečného externího vykonavatele ani placeného API.
