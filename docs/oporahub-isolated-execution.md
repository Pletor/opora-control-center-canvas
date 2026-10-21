# Izolovaný vykonavatel a doložená spotřeba — kontrakt 5b

Etapa 5b je implementována jako výslovně zapínaný serverový broker v Agent Office
a samostatná neměnná evidence v Canvasu. Deterministické HTTP testy a skutečný
Office → Canvas průchod se syntetickým poskytovatelem ověřují integrační chování.
[Skutečný průchod](oporahub-live-staging.md) na nakonfigurovaném Managed Agents účtu
proběhl 2026-10-21: context v2 skončil native výsledkem a potvrzeným ukončením;
původní context v1 zůstává zaznamenaným negativním případem bez receipt.
Dosavadní [časové rozpočty](oporahub-execution-budgets.md) a rezervace fungují;
návrat `pty.kill()` ani lokální přepis tokenů neprokazuje izolaci nebo fakturovanou
spotřebu. Rozhraní plánu a jeho přijetí zůstává v Canvasu.

## Zvolený rozsah

Samostatný registr vykonavatelů obsahuje volitelný adaptér Managed Agents.
Hostitelský CLI režim zůstává výslovně legacy. Chybějící konfigurace nebo ověření
prostředí vrací nedostupnost před claimem; izolovaný režim nemá CLI fallback.
Adaptér má vlastní lifecycle mimo synchronní CLI `ProviderAdapter.launch`.

Managed Agents poskytuje pro session samostatný Linux kontejner s nastavením
sítě. Připojené prostředí, agent a jeho instrukce musí být připnuté a ověřené;
název prostředí nebo pouhá přítomnost klíče nejsou důkazem aktivní izolace.
([Volba prostředí](https://platform.claude.com/docs/en/managed-agents/choosing-an-environment))

Tato etapa nezakládá účet, nemění globální ochrany Windows, nespouští Docker/WSL
ani nezadává placenou práci automaticky. Bez nakonfigurovaného prostředí a
ověřené capability vrací izolovaný režim nedostupnost. V aktuálním vývojovém
prostředí byl pro průchod výslovně nakonfigurován API přístup a vyhrazený cloudový
agent/prostředí. Pro toto cloudové vykonávání lokální Docker server není potřeba.

## Neměnný intent a obnova

Intent váže execution ID/epochu, accepted revision, assignment digest, původní
kontext a budget allocation, pevný deadline, repozitář a přesný commit SHA,
provider agent/environment ID a otisk konfigurace. Soukromé capability a klíče
nepatří do veřejného intentu, promptu, repozitáře ani logu.

Repozitář přináší také instrukční soubory; cloudový checkout musí odpovídat
výslovně připnutému commitu, nikoli novému pohyblivému HEAD.
([GitHub](https://platform.claude.com/docs/en/managed-agents/github))

Před externím požadavkem uložit intent. Session vytvořit bez počátečních událostí,
uložit její ID, znovu ověřit lease a teprve poté poslat práci. Po neznámém výsledku
create uložit `creation_unknown`; neprovádět slepé opakování, dokud není doložena
provider idempotence nebo nalezena původní session. Restart rekonciluje původní
mapping a nesmí automaticky založit náhradní placený běh.
([Session](https://platform.claude.com/docs/en/managed-agents/sessions))

## Zastavení a spotřeba

Ztráta oprávnění ihned zablokuje nové události a přijetí výsledku v Canvasu.
Adaptér vyžádá ukončení a ověří provider stav; `idle` ani přijatý interrupt není
potvrzené ukončení. Síťová chyba znamená `termination_pending/unknown`, ne úspěch.
Historii a artifacts zachovat; destruktivní odstranění session nenahrazuje audit.
Dokumentace neprokazuje přesné ukončení všech procesů v okamžiku lokálního deadline.
([Lifecycle](https://platform.claude.com/docs/en/managed-agents/session-operations))

Důvěryhodný broker čte provider API; worker nesmí dodat vlastní JSON a označit
jej za provider observation. Uložit scope, session/intent ID, čas, kumulativní
usage, bounded normalizovaný obsah a hash. Canvas ověří samostatnou observer
autentizaci oddělenou od worker lease tokenu. Replay stejného pozorování se
nezapočítá dvakrát; starší nebo neslučitelná observation nevrátí spotřebu.
([Pozorování usage](https://platform.claude.com/docs/en/managed-agents/session-observability))

Rozlišit tři veličiny: providerem doložené tokeny, provider `list_cost` a skutečnou
fakturu. Session budget zadat při vytvoření, nezvyšovat jej ani neodstraňovat.
Poskytovatel zastavuje nové model requests po dosažení ceníkového rozpočtu;
rozpracované požadavky a nástroje mohou limit přesáhnout. Ceníková cena není
faktura a není přesným invoice hard limitem. Vyžádá-li policy takovou garanci,
adaptér ji musí odmítnout jako nepodporovanou, nikoli ji nahradit odhadem.
([Budgets](https://platform.claude.com/docs/en/managed-agents/budgets))

## Důkazy dokončení

- Deterministické HTTP testy: create timeout, pád před/po mappingu, restart,
  přesná epocha a receipt, stop failure, opožděná usage, replay, zákaz fallbacku
  a úniku tajných údajů. Žádné placené volání v běžné sadě.
- Stejný přehled zobrazí skutečnou capability, stav ukončení a původ spotřeby;
  unavailable/unknown se nezobrazí jako ověřené.
- Samostatný provozní průchod na výslovně nakonfigurovaném účtu: izolovaná práce
  nad připnutým kódem, doložené ukončení a autentické provider usage. Bez něj
  nelze bod 11 označit za dokončený. Omezený živý průchod je nyní doložen výše;
  stále neopravňuje tvrdit přesné provozní SLA ani ověřenou fakturu.

Kontrakt zachovává meze poskytovatele. Nezmenšuje cílový rozsah goalu ani
nevydává hostitelský proces za izolovaný běh.

## Implementovaná rozhraní

Etapa 5b navazuje na publikovanou etapu 3b. Office má vlastní
registr `src/server/opora/executors/`; synchronní hostitelský `ProviderAdapter`
není rozhraním vzdálené session. Canvas poskytuje samostatné
`/api/oporahub/execution-observers`, nikoli rozšíření worker výsledku o tvrzení
„ověřeno“. Provozní nastavení a Office API popisuje
[dokumentace vykonavatele](https://github.com/Pletor/agent-office/blob/feat/oporahub-execution-authority/docs/opora-isolated-execution.md).

Izolovaný intent vyžaduje již přidělený execution budget v2 a váže jeho přesný
allocation ID i neměnný `runDeadlineAt`. Původní protokol rozpočtu pokusů a času
se kvůli tomu nepřepisuje. Oddělený provozovatelem nastavený cenový strop omezuje
kladný per-session `maxListCostCents`; jeho providerové vynucení má výše uvedené
meze. Nejde o rodinný fakturační hard cap. Požadavek přesné fakturační garance
je nepodporovaný a musí být odmítnut.

Pozorovatel má samostatný scoped serverový klíč. Podpis HMAC-SHA256 váže čas
a SHA256 přesných bytů těla; čas má okno 300 sekund a tělo nejvýše 128 KiB.
Worker lease token ani hlavička se jménem agenta jej nenahradí. Tajemství se
neposílá do promptu, browseru ani vzdáleného prostředí. API ukládá normalizované
kumulativní tokeny a cenové centy v USD, přesnou session a intent, sekvenci,
čas a otisk; replay se nezapočítá znovu. Jedna provider session nesmí financovat
dva různé intenty. Pozdní usage lze doložit i po konci lease, nikdy tím obnovit
oprávnění k práci. `terminated` vyžaduje skutečné provider readback; `idle`
není důkaz ukončení. Zápis má vlastní neměnnou historii a CAS hlavu.

Canvas server čte `OPORA_EXECUTION_OBSERVERS`: JSON mapu observer ID na objekt
`secret`, `project`, `workspace`, `provider: "anthropic-managed-agents"` a
`maxListCostCents`. Nejvýše 32 pozorovatelů, konfigurace 32 KiB, tajemství
32–512 UTF-8 bytů. Klíče patří pouze do serverového prostředí.
`POST /api/oporahub/execution-observers/intents` a `/observations` vyžadují
`x-opora-observer-id`, `x-opora-observer-time`, `x-opora-observer-signature`.
Podpis je hex HMAC-SHA256 zprávy `timestamp + "\n" + SHA256(rawBody)`.
`GET /api/oporahub/execution-observers?project=…&workspace=…` vrací veřejný přehled
pod stávající autorizací; nesděluje soukromou lease ani klíče.

Globální rezervace provider/session → intent se zapíše před projektovým důkazem.
Nejde o atomickou transakci dvou databází: osiřelá rezervace dovolí jen opakování
stejného intentu, nikdy přeřazení nebo automatické smazání. Chybějící registr při
obnově znamená odmítnutí důkazu. Limity jsou 65 536 rezervací / 64 MiB globálně,
16 MiB projektové evidence a 2 048 pozorování na intent; historie se neodřezává.

Nové DDL změní coverage dříve zapsaného context v2. Takové zápisy se odmítnou;
tato etapa neposkytuje nástroj pro změnu coverage ani re-enrollment.
Upgrade neprovádí reset. Historie, klíče a piny zůstávají zachované. Podmínky v1 platí.

Přehled ukazuje nejvýše dva stručné záznamy a otevírá stávající detail běhů.
Detail rozlišuje zdroj, čas, identitu intentu/session, nahlášený výsledek a
brokerem doloženou spotřebu. Nulová sentinelová usage bez session znamená
„nedoloženo“, nikoli nulu. Konfigurace pozorovatele neprokazuje přístup k provideru.
Výsledek z poslední zprávy agenta má přesnou vazbu na původní intent a receipt;
není nezávislým ověřením práce. Po ztrátě oprávnění lze nejistý receipt pouze
dohledat přes čtecí API, nikoli zopakovat zápis.

## Zaznamenané ověření implementace

Backend: 37 cílených testů prošlo; celá sada má 3 313 PASS, 4 skip a jednu
již známou chybu Graphify (`test_map_refresh.py`, unavailable místo watching).
Frontend po opravě odděleného detailu pozorování: 229 souborů / 1 595 PASS.
TypeScript, Vite a kopie fontů doběhly; PowerShell obal vrátil 1 kvůli stderr
varování Vite, nikoli zaznamenané chybě těchto fází. Tento rozdíl zůstává v logu.
Ruff má 56 shodných výchozích nálezů; nové backendové moduly jsou čisté.
Kontroly dokumentace a struktury nepřidaly nálezy ani nezvýšily limity.

Skutečný HTTP průchod Office → Canvas ověřil context v1/v2, budget v2, podepsané
čtení 187 centů / 342,5 aktivní sekundy, následný heartbeat, přesný receipt,
ukončovací readback a obnovu bez nové session nebo výsledku. Pouze provider byl
syntetický. To není důkaz provozní izolace ani skutečných účtovaných nákladů.

Headless browser ověřil skutečné podepsané záznamy, light/dark a mobil bez
vodorovného přesahu. Zachovaný filtr nativní historie jiné karty nezakryl
samostatný detail zvoleného pozorování: Office context 2 → context 1 i původní
running → terminated zobrazily právě jeden požadovaný detail a žádný cizí nativní
detail. Esc zavřel drawer. Jediný očekávaný HTTP/console záznam je fixture-only
Archify GET 409 bez připojeného zdrojového adresáře; jiné chyby nebyly zaznamenány.
