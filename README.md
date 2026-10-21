# Opora Canvas

Plátno projekt → sektor → uzel pro řízení agentů: struktura práce, zadání uzlů, podklady a běhy na jednom místě.

## Spuštění jedním příkazem

```sh
npm ci && uv sync      # jednou
uv run opora           # nebo: npm start
```

Nastavení běhu je v [opora.toml](opora.toml): port, adresář dat, sestavení frontendu, profily a integrace.
`uv run opora` sestaví frontend, když chybí nebo je starší než zdroje, spustí backend na http://127.0.0.1:8740/ a otevře prohlížeč.

- `uv run opora --profile preview` – náhled nad kopií dat (port 8790, `.data/preview`).
- `uv run opora --profile dev` – jen backend pro `npm run dev` (Vite proxuje `/api`).
- `uv run opora --check` – vypíše výslednou konfiguraci bez spuštění.
- `uv run opora --port 8791 --data .data/kopie --no-open --no-build` – jednorázové přepisy.
- `[app] embed_origins` – přesné původy, které smí Oporu zobrazit ve svém `<iframe>` (viz níže). Výchozí `[]` = rámování zakázané.
- Lokální přepisy mimo git: `opora.local.toml` se stejnou strukturou (např. `[app] data` mimo repozitář; přesun dat: `uv run python tools/move_data_root.py <starý> <nový> [--dry-run]`). Tajemství (API klíče) patří do proměnných prostředí, ne do TOML.

## Vložení do jiné lokální aplikace (`embed_origins`)

Opora se normálně nedá vložit do `<iframe>` (`X-Frame-Options: DENY`, CSP `frame-ancestors 'none'`), aby ji cizí stránka nemohla překrýt a podstrčit uživateli kliknutí (clickjacking). Chcete-li ji zobrazit ve vlastní lokální aplikaci, například v 3D kanceláři agent-office, vyjmenujte její původ v `opora.local.toml`:

```toml
[app]
embed_origins = ["http://localhost:4600"]
```

- Každá položka je přesný původ: schéma `http`/`https`, host a volitelně port. Cesta, dotaz, hvězdička ani `null` nejsou dovolené; neplatná položka zastaví start s českou hláškou (`uv run opora --check` ji ukáže hned).
- Neprázdný seznam vynechá `X-Frame-Options` a pošle `frame-ancestors 'self' <původy…>`. Ostatní CSP i hranice zůstávají: povolené Hosty, stejný Origin pro zápisy, cookie člověka `SameSite=Strict`, lease karet.
- **Bezpečnost:** nastavení uvolňuje ochranu proti clickjackingu jen pro vyjmenované původy. Uvádějte jen loopback původy (`localhost`, `127.0.0.1`) aplikací, které sami provozujete; nikdy veřejnou adresu.
- Cookie člověka je `SameSite=Strict`, takže zápisy z vložené Opory fungují jen tehdy, když je rám ze stejného webu jako rodič: z `http://localhost:4600` vkládejte `http://localhost:8740`, ne `http://127.0.0.1:8740`.
- Vložená Opora předává rodiči Escape, který sama neobsloužila (`preventDefault`): `window.parent.postMessage({ type: "opora:escape" }, <původ z document.referrer>)`. Bez referreru ani mimo rám se nic neposílá. Rodič má zprávu přijmout jen od původu Opory a sám rozhodne, co zavře. Panely Opory, které Escape zavírají bez `preventDefault`, ho předají také.

## Kde co je

- Pravidla umístění nového souboru: [docs/pravidla-struktury.md](docs/pravidla-struktury.md).
- Produktový kontrakt: [docs/PRODUCT-CONTRACT.md](docs/PRODUCT-CONTRACT.md).

## OporaHub a práce agentů

Canvas s OporaHubem drží plán, GitHub kód; agent-office je připojený vykonavatel.
V Alt+3 se otevře [jednostránkový přehled](docs/oporahub-overview.md): přijatý plán,
návrhy čekající na rozhodnutí, práce agentů, důkazy a další kroky. Konkrétní položka
otevře svůj detail; ✕ nebo Esc vrátí přehled. Výchozí obrazovka nezobrazuje dlouhé
formuláře. [Návrhový artefakt Claude Code](docs/design/README.md) je samostatná
klikací ukázka; aplikace používá skutečná data a stejné API jako agenti.

Přes **Upravit zadání karty** otevřete změny zadání, prohlédněte uložená zadání a jednou přijměte jejich
výchozí základ. Pak upravte cíl, omezení a akceptace vybrané karty v návrhu. Uložení
návrhu Canvas nemění; po prohlídce rozdílu ho může člověk výslovně přijmout do zadání.
Náhled rozlišuje přijaté, pracovní a navržené hodnoty. Přijetí není ověření kódu.

API `/api/oporahub/changesets` poskytuje kontext, neměnné návrhy a jejich přijetí;
`/api/oporahub/baselines` zakládá počáteční přijatou revizi. Zastaralá očekávání se
odmítají, agent může navrhovat, nemůže přijímat. Historické snímky uložených zadání
z `/api/oporahub/proposals` a původní Oracle dashboard zůstávají pod novým panelem.

Panel návrhů grafu vytváří nové karty, sektory, oblasti a vazby včetně prvního
plánu na prázdném plátně. Člověk před přijetím prohlédne neměnný návrh a při
prvním převzetí výslovně potvrdí základ grafu. Přijetí uloží graf i zadání v jedné
databázové transakci; agent může následně převzít přijatou kartu. Postup a omezení:
[návrhy grafu](docs/oporahub-graph-proposals.md).

Existující prvky lze upravit nebo výslovně odstranit v návrhu se zobrazením
přijatého, pracovního a navrženého stavu. Starší neprázdné plátno lze nejprve
převzít bez přidávání pomocné karty. Historie odstraněných karet a výsledků se
zachovává; nesouvisející pracovní změny se neschvalují. Postup:
[změny přijatého grafu](docs/oporahub-graph-changes.md).

Panel **GitHub důkazy** navíc
načítá review a kontroly přímo z GitHubu a váže je na konkrétní přijatou revizi a SHA.
Odděluje review kódu, review zadání a pozorované kontroly; neposkytuje automatické
povolení k merge. Soukromý repozitář vyžaduje token v prostředí serveru
(`OPORA_GITHUB_TOKEN`, případně `GH_TOKEN`/`GITHUB_TOKEN`). Podrobnosti a postup:
[GitHub důkazy](docs/oporahub-github.md).

Člověk může nastavit verzovaná [pravidla review a kontrol](docs/oporahub-review-policy.md):
přesné aplikace a názvy povinných kontrol, účty reviewerů, počty schválení a stáří
důkazů. Změna pravidel vyžaduje nové načtení; novější nedokončený nebo neúspěšný
pokus zneplatní aktuální použitelnost starého úspěchu. Historie zůstává dostupná.

[Trvalé sledování PR](docs/oporahub-reconciliation.md) po zapnutí člověkem obnovuje
úlohy i po restartu a zaznamená merge k původní revizi plánu. Odděluje stav úlohy,
pozorovaný stav PR a review; neslouží jako automatické dokončení karty. Sledování
běží v backendu i se zavřeným prohlížečem.

Agent-office přebírá neměnné zadání přes nové execution API. Rostoucí číslo
převzetí brání starému běhu odevzdat výsledek po ztrátě rezervace; opakované
odeslání stejného výsledku se neduplikuje. Historie běhů odlišuje odevzdání od
ověření. Nasazení, API a omezení: [vykonávání zadání](docs/oporahub-executions.md).
Pravidla rezervací mají také [omezený TLA+ model](tools/formal/oporahub-execution/README.md)
s reprodukovatelnou kontrolou a záměrně porušenou variantou.

[Pravidla běhů](docs/oporahub-execution-budgets.md) přidávají lidsky nastavený
pevný konec oprávnění a trvalý počet pokusů a oprav pro kartu a přijatou revizi.
Změna vlastníka, restart, uvolnění rezervace ani nová pravidla nevracejí spotřebu.
Po zařazení karty musí vykonavatel používat budget protokol v2; starší Office
se zastaví při převzetí. Jde o oprávnění a počet spuštění, nikoli peněžní limit
nebo záruku ukončení všech potomků procesu.

Verzované změny dalších druhů obsahu, řídký kontext podle závislostí,
rozpočty běhů a obecné spouštění Lean/TLA+ zůstávají další prací.
Historie se nemaže. Přesné API, migrace a omezení:
[kontrakt OporaHubu](docs/oporahub.md).
