# GitHub důkazy v OporaHubu

OporaHub umí uložit pozorování PR, review a kontrol pro konkrétní přijatou revizi
zadání a plné Git SHA. Pozorování je historický důkaz s časem načtení. Samo nepřijímá
návrh zadání, nemerguje PR, neuzavírá kartu a nepotvrzuje nasazení.

## Použití

1. V projektu připojeném ke GitHubu přijměte výchozí zadání v panelu Změny zadání.
2. V OporaHubu otevřete GitHub důkazy a zadejte číslo PR tohoto repozitáře.
3. Výslovně načtěte pozorování. Server získá SHA, review i kontroly z GitHubu;
   nepřebírá klientem zaslaný výsledek „schváleno“ nebo „testy prošly“.
4. Zkontrolujte revizi zadání, plné SHA, čas a oddělené výsledky review kódu,
   review zadání a pozorovaných kontrol. Historie načítá nejvýše 100 stručných
   záznamů; plné důkazy se čtou až v detailu.
5. Po změně PR data načtěte znovu. Není zde webhook ani periodická synchronizace.

Lokální návrh bez GitHubu zobrazí vysvětlení; pro práci s návrhy zadání GitHub
není podmínkou. Import vyžaduje zapisovatelný workspace, existující přijatou revizi
a shodu konfigurace repozitáře. Cílová větev PR musí odpovídat větvi projektu.

Server čte token při startu v pořadí `OPORA_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`.
Bez něj může číst veřejná dostupná data. Pro soukromý repozitář a ověření oprávnění
reviewerů potřebuje účet/token s odpovídajícím přístupem ke čtení daných GitHub API.
Token patří do prostředí serveru, nikoli do formuláře nebo repozitáře. Změna tokenu
vyžaduje restart serveru. Tato integrace provádí pouze GET požadavky.

## Projekt z lokální složky

Projekt, jehož zdrojem je lokální složka, nemá repozitář v metadatech, a proto pro
něj GitHub důkazy, trvalé sledování PR ani merge běhů nefungovaly
(„Projekt nemá připojený Git repozitář.“). Je-li složka Git checkout s GitHub
`origin`, člověk ji jednou připojí:

1. V OporaHubu otevřete Trvalé sledování GitHub PR. U projektu ze složky je nahoře
   karta „GitHub repozitář složky projektu“ předvyplněná repozitářem z `origin`.
2. Zkontrolujte repozitář (`owner/název`) a větev (obvykle `main`) a zvolte
   „Připojit repozitář“.

Server připojení ověří na disku: `git remote get-url origin` musí ukazovat na
stejný GitHub repozitář a větev musí existovat (`refs/remotes/origin/<větev>` nebo
`refs/heads/<větev>`). Uloží ho do registru jako metadata projektu
(`project_repository_bindings`); od té chvíle ho čte `configuration()` stejně jako
repozitář klonovaného projektu. Adresa z požadavku nikdy autoritu nedává.
Pracovní prostor se nemění: projekt ze složky dál pracuje v `draft`.

Připojení zároveň vrátí do fronty PR, která agent připojil k běhům dřív, než měl
projekt repozitář (`enrollment: unavailable`, `github-not-configured`). Smyčka je
při dalším průchodu zapíše do sledování, a už sloučená PR tak projdou merge,
zápisem do plánu i rozhodnutím `close_card`. Běhy bez připojeného PR najde
pravidelné hledání trailerů `Opora-Execution` / `Opora-Revision`.

API (jen lidská relace, cookie `opora_ui` a stejný origin; agent dostane 403):

- `GET /api/oporahub/repository?project=…` vrací `applies`, `bindable`,
  `binding`, `detectedRepository`, `canConfigure` a `unavailableReason`.
- `POST /api/oporahub/repository` s `{"project", "repository", "branch"}` připojí
  repozitář; opakování se stejnými hodnotami nic nemění, jiný repozitář vyžaduje
  nejprve odpojení. Odpověď nese `requeuedLinks`. Opakované připojení vrátí do fronty
  i odkazy, které selhaly kvůli nedostupnému GitHubu nebo chybějícímu tokenu
  (`github-unavailable`, `github-auth-missing`): po nastavení `OPORA_GITHUB_TOKEN`
  a restartu stačí repozitář připojit znovu.
- `POST /api/oporahub/repository/unbind` s `{"project"}` připojení zruší. Existující
  sledování pak hlásí změnu konfigurace a čeká na člověka.

Změní-li se později `origin` složky, připojení se samo nepřepíše; odpojte ho
a připojte znovu.

## Co jednotlivé výsledky znamenají

**Review kódu:** server ověřil schválení pro přesné SHA od jiného GitHub účtu typu
User než autora PR. Účet musí mít doložené oprávnění k zápisu, maintain nebo admin.
Lokální jméno agenta ani `author_association` nejsou dokladem tohoto oprávnění.
Novější rozhodnutí, zamítnutí, dismissal a neznámá oprávnění mohou kladný výsledek
zneplatnit. Komentář sám nenahrazuje předchozí rozhodnutí reviewera.

**Review zadání:** kromě podmínek review kódu musí schvalující review obsahovat
samostatný přesný řádek, který zobrazuje OporaHub:

```text
Opora-Plan: <project>/<workspace>@<acceptedRevision>
```

Řádek pouze v editovatelném popisu PR nestačí. OporaHub review za člověka neodesílá.
Přijatá revize zahrnuje zadání a při přijetí grafu také jeho verzovaný manifest.
Tento snímek sám neprokazuje nezávislost reviewera na autorovi původního zadání.
Propojení lidí Canvasu s ověřenými GitHub účty a počítání různých lidí v bráně
automatického review popisuje [registr identit](oporahub-review-identity.md).

**Pozorované kontroly:** jde o výsledky načtených check runs a commit statuses.
Jejich úspěch není potvrzením úplnosti povinných kontrol ani důvěryhodnosti všech
poskytovatelů CI. Toto pozorované hodnocení nadále vrací `policyVerified: false`.
Samostatné [vyhodnocení pravidel](oporahub-review-policy.md) používá člověkem
nastavené povinné kontroly a identity aplikací. Žádné kontroly nebo pouze
skipped/neutral výsledek neznamenají úspěšné ověření.

**Stáří:** změna přijaté revize, konfigurace cílové větve nebo posledního známého
SHA zneplatní použitelnost starého hodnocení. Shoda s posledním pozorováním není
tvrzení o živém GitHubu. Při neúspěšné obnově zůstane v historii také neúspěšný
pokus; starý úspěch nenahrazuje aktuálně nedostupná data.

## API a uchování dat

- `GET /api/oporahub/github-evidence?project=...&workspace=...` vrací aktuální
  přijatou hlavu, dostupnost integrace a stručnou historii s odvozeným hodnocením.
- `POST /api/oporahub/github-evidence` přijímá `project`, `workspace`,
  `expectedAcceptedHead`, `prNumber` a volitelně `expectedHeadSha`. Iniciátora
  určuje middleware. Agent smí načíst důkazy, tím však nezískává právo přijímat plán.
- `GET /api/oporahub/github-evidence/{id}?project=...&workspace=...` načte plný
  neměnný snímek a jeho hodnocení vůči aktuálnímu místnímu kontextu.

Síťové požadavky probíhají mimo projektové zámky. Před zápisem se znovu kontroluje
revize a konfigurace. Změněný kontext vrací konflikt bez přepsání historie.
Nedostupné či neúplné GitHub odpovědi se zaznamenají jako `complete: false`, nikoli
jako kladný výsledek. Obsah a rozsah uloženého snímku chrání kontrola otisku.
Každé nové načtení má vlastní trvalé pořadí pokusu a vytvoří nový historický záznam,
i když vzdálené výsledky zůstaly stejné. Novější pokus určuje aktuální použitelnost
důkazů podle nastavených pravidel.

Transport používá pevný GitHub API origin, nepovoluje přesměrování a omezuje
velikost odpovědí, počet dotazů a stránek. Překročení limitu znamená neúplné
pozorování. PR se kontroluje před a po načtení souvisejících kolekcí; nejde však
o distribuovanou transakci s GitHubem.

## Automatické čtení pro uzavření smyčky

PR připojené k běhu ([uzavření smyčky](oporahub-executions.md#uzavření-smyčky-běh--pr--merge--plán))
server čte sám: jednou kvůli číselné identitě PR při zapnutí sledování a pravidelně
jednu stránku nedávných PR kvůli trailerům `Opora-Execution` a `Opora-Revision`.
Používá stejný transport s pevným originem, bez přesměrování, s limity velikosti
a s respektem k rate limitu. Bez GitHub repozitáře projektu nečte nic (projekt
z lokální složky ho získá [připojením](#projekt-z-lokální-složky)). Ani tato
čtení nevytvářejí review důkaz, nepřijímají plán a nic na GitHub nezapisují.
U otevřených připojených PR server stejně čte také check run `formal/tlc` na head SHA
a převádí ho na záznam formálního ověření
([automatické ověřování v CI](oporahub-verification.md#automatické-ověřování-v-ci-etapa-3b)).

Podklady API: [review](https://docs.github.com/en/rest/pulls/reviews),
[oprávnění](https://docs.github.com/en/rest/collaborators/collaborators),
[check runs](https://docs.github.com/en/rest/checks/runs).
Celkový kontrakt a další etapy: [OporaHub](oporahub.md).
