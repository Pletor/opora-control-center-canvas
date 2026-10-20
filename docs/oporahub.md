# OporaHub: verzované plány, návrhy změn a review

Rozhodnutí 2026-10-20: **Canvas s OporaHubem drží platný plán, GitHub drží kód.**
Agent-office vykonává práci přes API; OporaHub funguje i bez spuštěné 3D kanceláře.
Tento kontrakt nahrazuje předchozí rozhodnutí z 2026-10-04 o GitHubu jako jediném
zdroji pravdy pro plány, včetně požadavku zrušit historii OporaHubu. Při rozporu
má pro plány přednost i před `docs/synchronizace-pravdy.md`. Existující kontroly
Oracle a vazby na kód se zachovávají do jejich ověřené migrace.

## Odpovědnost a principy

| Součást | Vlastní |
|---|---|
| Canvas | Zadávání, vizuální plán, závislosti a rozhodování člověka |
| OporaHub v backendu Canvasu | Historii plánů, návrhy změn, konflikty, review a vazby na důkazy |
| agent-office / CI | Izolované vykonání úkolu, testy, model checkery a vrácení výsledků |
| GitHub | Kód, testy, formální modely, PR a historii implementace |

Canvas a agenti používají stejný plán přes API; Canvas není další nezávislá databáze
pravdy. Export plánu do repozitáře může sloužit jako artefakt, nikoli jako automatický
přepis platného plánu při rozporu.

Ze [Scionu](https://www.anthropic.com/research/redesigning-source-control) přebíráme
serverové operace přes API, neměnné changesety s rodičem a načítání potřebného rozsahu.
Z Antique přebíráme oddělené rozhraní review. [Článek o review Claude Code](https://claude.dev/blog/solving-code-review-at-anthropic/)
je další podklad pro průběžné nezávislé kontroly; není specifikací Antique.
Níže uvedené etapy jsou návrh Opory, nikoli tvrzení o totožné implementaci Anthropic.

## První etapa: dostupné API

Tato etapa přidává serverové snímky **již uloženého zadání**. Návrh zatím neumí
přijmout libovolný patch, izolovat rozpracované změny ani změnu schválit. Uložení
zadání v Editoru stále předchází vytvoření návrhu; kompletní oddělení pracovní
verze od přijatého plánu toto starší API neposkytuje; pro změny zadání použijte druhou etapu níže. Prostředí Alt+3 nabízí výběr rozsahu, důvod a vytvoření návrhu, historii a rozdíl proti rodiči. Pod nimi zůstává synchronizační dashboard. Úplné review se schvalováním zatím není implementováno.

1. Uložte zadání existujícími funkcemi Canvasu.
2. Načtěte `GET /api/oporahub/context?project=<id>&workspace=draft&scope=<id>`.
   Odpověď obsahuje `head` (ID nebo `null`), `scope`, `specRevision`, `graphDigest`,
   `contextVersion` a `specification`.
3. Pošlete `POST /api/oporahub/proposals` s tímto tělem:

   ```json
   {
     "project": "projekt",
     "workspace": "draft",
     "scope": "uzel",
     "subject": "Upřesnění akceptace",
     "expectedHead": null,
     "expectedContextVersion": "<contextVersion z předchozí odpovědi>"
   }
   ```

   `expectedHead` musí obsahovat skutečné načtené ID; `null` patří jen k prázdné
   historii. Obě očekávání jsou povinná. Server pod zámkem ověří hlavu historie
   i verzi zadání a sám zachytí uložený obsah. Zastaralý požadavek odmítne `409`;
   klient načte nový kontext a přehodnotí návrh, neopakuje zápis naslepo.
   Autora určuje existující middleware identity (session člověka nebo identita
   agenta), nikoli klientské pole `by`. Chybějící identita vrací `428`.
4. Odpověď obsahuje neměnný záznam s `id` a `specificationSnapshot`. Historii dál
   čte `GET /api/opora-commits` se stejnými parametry rozsahu.
5. Dva uložené snímky porovná
   `GET /api/oporahub/diff?project=<id>&workspace=draft&scope=<id>&before=<id>&after=<id>`.
   `changes` obsahuje operace `add`, `remove`, `replace`, cesty JSON Pointer a
   příslušné hodnoty `before`/`after`. Pole se porovnávají jako celek.

Agent smí vytvořit návrh, **nesmí ho sám mergovat**. Návrh není schválení plánu,
implementace ani důkaz splnění. Legacy commit a merge vyžadují session člověka (agent dostane `403`); autor z těla požadavku se ignoruje. Merge ověří aktuální hlavu a shodu uloženého snímku s živým zadáním před existující bránou Oracle. Starý záznam bez snímku se nemerguje;
nové nezávislé review ještě není implementováno.

Kontext využívá existující zachycení specifikace včetně souvisejících karet a celého
strukturálního grafu. Není ještě plně úsporným načítáním podle závislostí: i nesouvisející změna strukturálního grafu může konzervativně zneplatnit kontext návrhu. Odkazy
na externí podklady nejsou důkazem přečtení jejich obsahu. Historický diff používá
uložené snímky, nikdy současný Canvas jako náhradu minulosti. Záznam bez snímku
vrací při diffu `409`; chybějící minulý obsah nelze zpětně vymyslet.

## Druhá etapa: oddělené návrhy změn zadání

OporaHub nyní podporuje neměnné návrhy nad poli `goal`, `non_goals`, `acceptance`
existujících karet. Návrh nemění pracovní Canvas. Přijetí člověkem zapíše dotčená
zadání a přijatou revizi atomicky. Přijatá revize v této etapě zahrnuje **pouze
zadání**, nikoli celý graf, texty, kresby nebo úplný kontext projektu.

V Alt+3 je nový panel **Změny zadání**. Nejprve zobrazí všechna výchozí uložená zadání
k prohlídce; člověk s uvedeným důvodem výslovně přijme tento základ. Základ lze založit
jen jednou, tlačítko není cestou k hromadnému přijetí pozdějších pracovních změn.

Po založení základu vyberte kartu a upravte její cíl, omezení a podmínky dokončení.
Text zůstává v lokálním návrhu; **Uložit návrh změny** pouze vytvoří changeset. Pokud
Canvas obsahuje dřívější nepřijaté úpravy, lze takto navrhnout jejich cílené přijetí
i bez další změny textu. Náhled proto ukazuje tři hodnoty: přijaté zadání, pracovní
zadání v okamžiku návrhu a navržené zadání. Teprve **Přijmout zobrazený návrh do zadání**
změní Canvas. Nejde o nezávislé review, schválení implementace ani zelené CI.

Obnova kontextu a přepnutí karty zahazují rozepsanou lokální úpravu, jak uvádí UI.
Po úspěchu i odmítnutí zápisu je další obnova výslovná; klient nemění očekávání ani
neopakuje mutaci automaticky. Starší návrh lze výslovně převést na aktuální přijatou
revizi: vznikne nový neměnný návrh, původní zůstává. Konflikt stejné karty se tím
nesmí skrýt; pokud neplatí předpoklady, server převod odmítne.

| API | Vstup a význam |
|---|---|
| `GET /api/oporahub/changesets/context` | `project`, `workspace`; vrací `acceptedHead`, `graphDigest`, `specificationsVersion`, pracovní `documents`, `acceptedDocuments` a `workingDiffers` |
| `POST /api/oporahub/baselines` | Session člověka, `project`, `workspace`, `subject`, `expectedAcceptedHead: null`, `expectedGraphDigest`, `expectedSpecificationsVersion`; počáteční přijetí uložených zadání |
| `POST /api/oporahub/changesets` | Člověk nebo agent; `project`, `workspace`, `subject`, `parentRevision`, `expectedGraphDigest`, `changes: [{nodeId, expectedRevision, fields}]`; plná tři textová pole, skutečná pracovní revize karty |
| `GET /api/oporahub/revisions/{id}` | `project`, `workspace`; neměnný záznam základu nebo přijetí včetně rodiče a dokumentů |
| `GET /api/oporahub/changesets` | `project`, `workspace`; seznam návrhů a aktuální přijatá hlava |
| `GET /api/oporahub/changesets/{id}` | `project`, `workspace`; neměnný návrh s rodičem, autorem, změnami a odvozeným stavem `accepted` |
| `POST /api/oporahub/changesets/{id}/accept` | Session člověka, `project`, `workspace`, `expectedAcceptedHead`; přijme pouze návrh splňující dokumentové a grafové předpoklady |
| `POST /api/oporahub/changesets/{id}/rebase` | `project`, `workspace`, `expectedAcceptedHead`; nový návrh nad aktuální přijatou revizí při nezměněných dotčených dokumentech |

Dokument obsahuje `nodeId`, `ownerWorkspace`, `revision`, `fields`. Změna obsahuje
`expectedRevision`, původní pracovní pole `before`, původní přijatý dokument `acceptedBefore`
a navržené `fields`. Tato data jsou podkladem historického porovnání; živý Canvas
nenahrazuje minulost. API podporuje více dotčených dokumentů v jedné změně,
UI zatím vytváří návrh pro jednu kartu.

Nové karty po založení základu zatím nelze přidat do přijatého plánu. Změny grafu,
vazeb a dalších druhů obsahu jsou další etapa; jejich konzervativní kontrola může
vyžadovat nový návrh i při nezávislé změně struktury. Starší snímky uložených zadání
z první etapy mají vlastní panel a historii, nejsou automaticky přijatými changesety.

## Další implementační etapy — zatím nejsou hotové

| Etapa | Výsledek | Podmínka dokončení |
|---|---|---|
| 2b. Celý graf návrhů | Rozšíření existujících změn zadání na karty, vazby, texty a sparse kontext | Dva nezávislé návrhy lze přijmout; rozpor stejného zadání se neztratí a vyžádá řešení |
| 3. Nezávislé review | Připomínky k rozdílu, role autora/reviewera, schválení revize plánu a Git SHA | Autor se nemůže sám nezávisle schválit; změna dotčeného zadání či SHA zneplatní odpovídající kontrolu |
| 4. Důkazy a GitHub | Záznam revize plánu + SHA + PR + kontrol, opakované doručení a obnova synchronizace | Výpadek mezi merge PR a zápisem do Canvasu neztratí výsledek; „schváleno“, „implementováno“, „ověřeno“ a „nasazeno“ jsou různé stavy |
| 5. Vykonavatelé | API pro agent-office/CI, rezervace s expirací, rostoucí fencing token, idempotency klíče a rozpočty | Starý agent po převzetí práce nástupcem nezapíše výsledek; opakovaný požadavek nezpůsobí dvojí akci |
| 6. Rozhraní | Canvas pro cíle a OporaHub pro rozdíly, review, konflikty a důkazy | Člověk dohledá od cíle přes změnu až k ověření; UI používá stejné API jako agent |
| 7. Formální ověřování | Oddělené vykonávání TLA+/Lean a dohledatelné artefakty | Kontrola uvádí model, tvrzení, předpoklady, verze nástrojů, výstup a vazbu na konkrétní kód |

Nezávislé lidské review vyžaduje rozlišitelné ověřené identity reviewerů. Současná lokální session „Člověk“ nedokládá dva různé lidi; jméno zaslané klientem to nenahradí. Důkazy musí rozlišovat výsledek potvrzený vykonavatelem od tvrzení samotného autora.

Automatické opravování musí mít limit kol, času a nákladů; po vyčerpání zobrazí
překážku místo nekonečného dialogu autor–reviewer. GitHub a Canvas nemají společnou
transakci: integrace potřebuje trvalé události, deduplikaci a periodické dorovnání.
Vrácení revize plánu samo nevrací kód ani nasazení.

TLA+ začíná modelem rezervací, souběžného přijetí změn a obnovy po pádu. Lean se
použije pro přesná tvrzení o kritických pravidlech. Modely a testy patří do GitHubu,
výsledky k revizi v OporaHubu, spouštění do agent-office/CI. **Důkaz modelu není
automaticky důkaz implementace v Pythonu či TypeScriptu.** Převod musí doložit
například diferenciální testy, které porovnají přechody implementace s modelem.
Formální ověřování není povinná kontrola každé úpravy UI.

## Migrace a ověření

Obě etapy jsou aditivní: nemaže soubory historie, `main.log`, index `opora_commits`
ani identifikátory karet. Staré záznamy zůstávají čitelné; nově zachycený snímek
nepředstírá znalost jejich původního obsahu. Existující čtečky a dashboard pokračují.
Žádný běžící vykonavatel se při tomto kroku automaticky nevypíná. Úložiště zapisuje nejprve soubor, potom SQLite index; nejde o společnou atomickou transakci. Při pádu indexu může trvalý soubor zůstat a index se obnoví funkcí `rebuild_index`.

Před budoucím přepnutím zápisů: záloha a inventura dat, převod na kopii, kontrola
ID a vazeb, ověření čitelnosti historie, teprve pak přepnutí a doložený návrat.
Rušení starého úložiště či synchronizace vyžaduje dokončenou migraci; není součástí
přidání proposal API.

Ověření změn: `uv run pytest backend`, `npm test`, `npm run build` a dostupná kontrola
TypeScriptu podle `package.json`. Změny vzhledu navíc vyžadují screenshot v headless
prohlížeči. API testy mají prokazovat odmítnutí zastaralého kontextu i hlavy,
serverový původ obsahu, neměnný historický diff a zákaz merge pro agenta.
