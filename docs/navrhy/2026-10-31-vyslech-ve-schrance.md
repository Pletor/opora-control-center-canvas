# Výslech ve Schránce: z požadavku zadání, ze zadání karty nebo narovnané milníky

Stav: návrh ke schválení (2026-10-31). Navazuje na `docs/navrhy/2026-10-30-vyslech-srdce.md` (výslech srdce) a `docs/navrh-schranka-zadani.md` (Schránka zadání).

## 1. Proč

Výslech srdce dnes běží ve vlastní tabulce `intake_briefs`. Má syntézu, otázky a výzkum, ale ze Schránky bere jen fragment výzkumu. Schránka přitom už umí všechno, co výslech potřebuje:
- doslovné a verzované fragmenty;
- dělení bez ztráty textu;
- výzkum s verdiktem `feasible | dead_end | unrealistic | unverified` a důkazy;
- „K upřesnění“ (`question` / `answer`, odpovídá člověk);
- bránu `synthesized` (`done`, `steps`, `nonGoals`, `checks`);
- MVP a rozpad do karet (`build_plan`), včetně doplnění existující karty (`existing_card`, `update_of`).

Dvě místa pro totéž znamenají, že člověk nevidí celek a karty nestojí na ověřených faktech. Proto jedno místo, a tím je Schránka.

## 2. Mapování (bez nové tabulky, bez změny schématu)

| Výslech dnes | Ve Schránce |
|---|---|
| požadavek `rq_…` | kořenový fragment `brief` (vznikne jím i vstup brány jako dnes) |
| syntéza: části | podfragmenty kořene (`split`), každá část s původem (citace z požadavku) |
| syntéza: předpoklady | podfragment s `question` „Platí, že …?“ |
| výzkum | `research` u části s verdiktem a důkazy (`research --fragment` už existuje) |
| otázky s doporučením | `question` u fragmentu; odpověď `answer` dává jen člověk |
| jasno (`clear`) | brána `synthesized` na kořeni s `done`, `steps` a `nonGoals` |
| karty | `build_plan` z fragmentů s `synthesized`: nové karty, nebo doplnění existující karty |

Řádek `intake_briefs` zůstane, ale jen jako ukazatel: stav, cena a `fragmentId` kořene. Velín ukáže stav a tlačítko **Otevřít ve Schránce**. Pokud stávající sloupce na `fragmentId` nestačí, zastavím se a zeptám se, protože šlo by o změnu schématu.

## 3. Pravidla reality (proti vzdušným zámkům)

1. Část bez výzkumu s verdiktem `feasible` (nebo s potvrzením člověka) nedostane `synthesized`, takže z ní nevznikne karta.
2. Výzkum s verdiktem `dead_end` nebo `unrealistic` z části udělá otázku pro člověka: „přeformulovat / zahodit / přesto“. Srdce o tom nerozhoduje samo.
3. Důkaz je odkaz na kód, soubor, PR nebo zdroj. Věta „mělo by jít“ důkazem není.
4. Strop ceny výzkumu zůstává `brain.brief.researchUsd`.

## 4. Narovnání milníku (nový průchod)

Vstupem je aktivní milník a jeho kritéria. Srdce projde karty milníku a ke každé najde fragment (`fragmentRef`). Pak každou kartu zařadí do jedné ze čtyř skupin:
- **stojí:** fragment má `synthesized` a výzkum `feasible`;
- **chybí:** karta nemá fragment, kroky ani `done`. Srdce založí fragment z karty (`from_idea`) a pošle ho stejnou cestou jako v §2;
- **vzduch:** karta stojí na výzkumu `dead_end` nebo `unrealistic`, nebo nemá žádný. Vznikne otázka pro člověka a karta zůstane `draft`, nikdo ji nepřevezme;
- **mimo:** karta nepřispívá k žádnému kritériu milníku. Srdce navrhne přesun do jiného milníku nebo zrušení. Rozhoduje člověk, nebo agent při plné autonomii.

Výsledkem je doplnění existujících karet (kroky, `done`, `non_goals`) přes `update_of`. Chráněná pole a brána uzavření karty zůstávají beze změny.

## 5. Řezy (každý = 1 malé PR)

1. **Výslech zapisuje do Schránky.** Požadavek vytvoří kořenový fragment, syntéza ho rozdělí (`split`), předpoklady a otázky se zapíšou jako `question` a `clarity` čte stav fragmentů. Velín dostane odkaz „Otevřít ve Schránce“.
2. **Pravidla reality** z §3 v `brief_vault_gate_rules.py`: bez verdiktu `feasible` nevznikne `synthesized`.
3. **Karty ze Schránky.** Srdce místo vlastního `plan` volá `build_plan` a doplňuje existující karty.
4. **Narovnání milníku** podle §4, jako příkaz srdce `straighten --milestone M` a jako tlačítko ve Velínu.

## 6. Co se nemění

- brána uzavření karty;
- chráněná pole;
- zeď (`gate_required`);
- odpověď na otázku dává jen člověk;
- data v `P:\opora-data` se zapisují jen přes API.

## 7. Poznámky k řezu 1

Řez 1 je write-through: spis výslechu zapíše svou transakci a teprve potom se zrcadlí do Schránky
(`backend/brain_opora/determinism/brief_vault_link.py`). Odchylky od §2 a §5:

- **`clarity` zatím čte spis** (`intake_briefs`), ne stav fragmentů. Schránka je v tomto řezu zrcadlo: odpověď
  na otázku nebo předpoklad zadaná přímo ve Schránce se do spisu nevrací, odpověď z Velínu do Schránky ano.
- **Kořen:** `situation.fragmentId` a `situation.fragmentScope` (rozsah Schránky pro „Otevřít ve Schránce“) v JSON
  spisu, bez změny schématu. Zakládající vstup ze Schránky (`brief_fragment`) se stane kořenem sám; jinak vznikne
  kořen `brief` na plátně (`scopeNodeId: ""`) s doslovným textem vstupu a disciplínou `cx` (kořen ji nést musí;
  přeřadí `set-discipline`). Kořen vzniká při `start`, po probuzení srdce spouštěčem výslechu a nejpozději při
  prvním `brief` / `ask`; je idempotentní. Obnova spisu odkazy do Schránky přenáší.
- **Smyčka vstupní brány:** zrcadlo píše přes `BriefVault.apply(..., intake=False)`, takže nový fragment `brief` /
  `question` nezaloží vstup brány (požadavek ho už má). Běžný zápis Schránky vstup zakládá dál.
- **Části syntézy** jsou podfragmenty kořene přes `create` s `parentId`, ne `split`: části nejsou výřezy textu
  požadavku a `split` hlídá, že se text neztratí. Párují se pořadím (`situation.partFragments`), změněný text =
  `revise` s `expectedRevision`. Část, kterou nová syntéza vypustí, ve Schránce zůstane (maže jen člověk).
  Původ (`origin`, `source`) je v poznámce revize.
- **Předpoklady** jsou otázky K upřesnění „Platí, že …?“ (`question`, pro člověka), spárované textem
  (`situation.assumptionFragments`); **otázky výslechu** jsou `question` s doporučením srdce jako návrhem
  (`situation.questionFragments`), odpověď člověka z Velínu jde jako `answer` za člověka.
- **Selhání Schránky** (např. pracovní prostor `main` jen pro čtení) se zaloguje a výslech pokračuje beze změny.
