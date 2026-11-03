# Eval „OPORA vs. bez OPORY“ – vstupní sada (12 případů)

Stav: návrh 2026-10-28. Zdroje: živá OPORA `:8740` (jen GET), Ample `I:\1. Projekty\01_ITNeskola\06_AmpleLab\ample`
@ `7e78d68`, kontrakty `docs/architektura-pro-agenty.md` (§3.1, §3.2, §4), `docs/cesta-zakaznika-a-brief.md`,
`docs/brana-cesty.md` (plán přehrání, `data-opora-section`).

**Varianty.** A = headless Claude Code se skillem `opora-control-center` a s vlastní (dočasnou) instancí backendu
OPORA s **prázdným** projektem (rozhodnutí 2026-10-28): aplikaci, stránky se `site.goal/feel/sections`, cesty,
karty a kroky si agent vytvoří sám v plátně a staví přes karty; harness mu jako člověk jednou zapne plnou
autonomii agentů. B = stejné repo, stejný text záměru, bez skillu a bez backendu.
Obě varianty dostanou **doslova stejný** text záměru včetně společné patičky (níže).

**Programová kontrola (společná pro všechny případy, pokud případ neříká jinak).**
1. `npm ci` (z cache) → `npm run build` exit 0 → `npm test` exit 0 (u Ample navíc žádný dříve zelený test nesmí
   zčervenat).
2. **Sekce:** pro každou sekci záměru na její URL právě jeden element `[data-opora-section="<id>"]`, viditelný,
   s nenulovou výškou; a v `src/` (Ample `frontend/`) existuje komponentový soubor `*.tsx`, který tento atribut
   renderuje (grep na literál nebo na mapu id → komponenta).
3. **Přechody cesty:** harness vygeneruje plán (`opora.journey-plan/1`) ze **skryté zlaté mapy** případu stejnou
   funkcí `journey_plan` a přehraje ho `tools/journey_run.py --dry-run --base-url http://127.0.0.1:<port>
   --fixtures <případ>.json` proti `vite preview` čisté kopie. Segment projde, když po akci (`click`/`submit`
   v `scope`, prvek podle `text`) pathname = `expectPath`. Pro variantu B se plán dodává jen harnessu, ne agentovi.
4. **Kritéria případu** (tabulka u případu): DOM/URL/ARIA tvrzení v Playwrightu, síť stubovaná
   `page.route(...)`, žádné reálné API.
5. **Slepý párový soudce:** dostane záměr, diff A a diff B (náhodné pořadí, bez stop skillu/OPORY v diffu – soubory
   `.opora/`, logy a zmínky o kartách se z diffu vyřadí) a screenshoty URL sekcí; volí lepší + skóre 1–5 za
   „věrnost záměru (goal/feel/moves)“, „čitelnost struktury“, „stavy a chyby“.

**Společná patička záměru (přidá se k textu každého případu, A i B):**
> Každý kořenový element sekce nese atribut `data-opora-section="<id sekce>"` (id jsou v závorkách výše).
> Projekt musí po práci projít `npm run build` a `npm test`. Pracuj jen v tomto repozitáři, nic nenasazuj.

## Přehled

| id | tags | zdroj | obtížnost | co se kontroluje programově |
|---|---|---|---|---|
| C01 | `[1-stranka, lehky, pestovani]` | fixture Pěstování (`test_journey_plan.py`) | lehký | build/test; route `/pribeh`; 4 sekce; `cta` má `<a href="/">` s textem „Chci začít pěstovat“ |
| C02 | `[formular-chyba, stredni, kontrakt]` | `architektura-pro-agenty.md` §3.1 (`/kontakt`) | střední | prázdné/chybné odeslání → `role=alert` v sekci `form`, `aria-invalid`, URL beze změny; platné → `/dekujeme` |
| C03 | `[vice-stranek-cesta, tezky, pestovani]` | cesta „Kampaň Pěstování“ (`brana-cesty.md`, `test_journey_plan.py`) | těžký | 4 segmenty plánu (nav, submit, body, odbočka `cta`) projdou; 3 routy; 6 sekcí |
| C04 | `[rozsireni, lehky, pestovani]` | Pěstování, stránka Novinky | lehký | nová sekce `archiv` + filtr; regrese: všechny 4 segmenty C03 dál projdou |
| C05 | `[uprava-cesty, stredni, pestovani]` | Pěstování + nový krok `/kurz` | střední | nový plán (5 segmentů) projde; přechod s2→s3 jen ze sekce `clanek` s textem „Přečíst příběh“ |
| C06 | `[vice-stranek-cesta, tezky, kontrakt]` | `architektura-pro-agenty.md` §3.2 (Prodej kurzu) | těžký | 5 rout; 4 segmenty vč. odbočky `mini` z prodejní stránky; submit s daty fixture |
| C07 | `[vice-stranek-cesta, formular-chyba, tezky, kontrakt]` | §4 (Poptávka zahrady) | těžký | 2 segmenty; stub `POST /api/poptavka` 500 → chyba a data zůstanou; 200 → `/dekujeme`; stav „odesílá“ |
| C08 | `[formular-chyba, rozsireni, stredni, ample]` | Ample `/login` | střední | nová veřejná routa `/zapomenute-heslo` bez AuthGate; segment `/login`→`/zapomenute-heslo`; chyba e-mailu; feature složka |
| C09 | `[rozsireni, lehky, ample]` | Ample `/` (ProjectsPage) | lehký | 3 existující sekce označené + 1 nová `napoveda` s odkazem na `/settings/organization`; žádný existující test nezčervená |
| C10 | `[vice-stranek-cesta, formular-chyba, tezky, ample]` | Ample `/` → `/settings/team` | těžký | segment z nové sekce na `/` do `/settings/team`; pozvánka 409 → chyba v sekci `pozvanky`; stuby `/api/v1/**` |
| C11 | `[1-stranka, lehky, pestovani]` | Pěstování, stránka Novinky | lehký | route `/novinky`; 4 sekce; `faq` přes `<details>`; 3 karty článků; odkaz `/pribeh` |
| C12 | `[uprava-cesty, stredni, kontrakt]` | výsledek C06 + úprava | střední | krok `mini` zrušen (žádný `href="/miniupsell"`), nový `via` do `/upsell`, nová sekce `faq`; nový plán projde |

Rozložení: lehký 4 (C01, C04, C09, C11), střední 4 (C02, C05, C08, C12), těžký 4 (C03, C06, C07, C10).
Typy: 1-stránka 2, víc stránek s cestou 4, formulář s chybou 4, rozšíření 3, úprava cesty 2 (případ může mít dva).

## Výchozí repozitáře

| kód | co | stav |
|---|---|---|
| `T0` | minimální šablona Vite 6 + React 19 + react-router-dom 7 + TypeScript 5 + Vitest 3 (`src/main.tsx`, `src/App.tsx` s jedinou routou `/` → „Rozpracováno“, `src/App.test.tsx` 1 test, `index.html`, `package-lock.json`) | **zatím neexistuje**; vytvořit jednou do `backend/brain/evals/opora-vs-bare/templates/vite-min/`, zamknout lockfile, git init s jedním commitem |
| `T1` | `T0` + zlatá (ručně psaná) realizace C03 (stránky `/`, `/novinky`, `/pribeh`, sekce s `data-opora-section`) | vytvořit jednou, commit; cesta C03 musí na ní projít |
| `T2` | `T0` + zlatá realizace C06 (5 stránek prodeje kurzu) | vytvořit jednou, commit |
| `AMP` | Ample @ `7e78d68f476a6e317e678d2541999971311fbc5b` přes `git archive` (ne pracovní strom: ten má necommitnuté změny v `backend/`), bez `node_modules`, `dist/`, `graphify-out/`, `archify-out/`, `image*.png`; `npm ci` z cache | Node ≥ 22; spouští se jen frontend (`vite`, port z harnessu), API stubované v Playwrightu |

Zlatá mapa (`seeds/<případ>.json`, sekce „Zdrojová data“): uzel aplikace, stránky se `site` a u cest
`site.journeys`. **Agent A ji nedostává**; slouží jen graderu k plánu přehrání cesty. Rameno A začíná nad
prázdným projektem. U `T1`/`T2`/`AMP` (rozšíření) se rozhodne při převodu, zda A dostane mapu hotové realizace.

---

## C01 – Příběh (jedna stránka)

**Záměr (A i B):**
> Postav stránku „Příběh“ na adrese `/pribeh` pro web o pěstování zeleniny na balkoně. Cíl stránky: návštěvník
> uvěří, že pěstování zvládne i začátečník, a klikne na „Chci začít pěstovat“. Pocit: osobně, povzbudivě.
> Sekce: úvod s nadpisem a krátkým perexem (`hero`), příběh autorky ve třech odstavcích od prvního neúspěchu po
> plný balkon (`pribeh`), tři krátké citace čtenářů (`dukaz`), výzva s odkazem „Chci začít pěstovat“ na hlavní
> stránku `/` (`cta`). Texty si vymysli, žádná skutečná jména.

**Zdrojová data:** stránka `pribeh` (fixture `test_journey_plan.py`, `path=/pribeh`); `goal` „Návštěvník uvěří, že
to zvládne, a klikne na Chci začít pěstovat“; `feel` „osobně, povzbudivě“; sekce `hero` (hero), `pribeh`
(content), `dukaz` (proof, `moves`: „Rozptýlí obavu ‚na to nemám talent‘ hlasy začátečníků“), `cta` (cta). Cesta:
žádná.

**Výchozí repo:** `T0`.

**Očekávané koncové stavy:**
- `npm run build`, `npm test` exit 0; routa `/pribeh` vrací stránku (ne fallback).
- 4 sekce `hero`, `pribeh`, `dukaz`, `cta` na `/pribeh`, v tomto pořadí v DOM; `dukaz` obsahuje ≥ 3 `blockquote`
  nebo `figure`.
- `[data-opora-section="cta"] a[href="/"]` s přístupným jménem „Chci začít pěstovat“.
- Členění (každá sekce v samostatné komponentě `*.tsx`) je jen informativní metrika `clenenis`: zadání ho
  nežádá, proto není v `checks_pass` (metriky.md Q1, rozhodnutí 2026-10-28).

**Proč je těžký:** není; kalibrační případ – rozdíl A/B tu má být malý, jinak eval měří režii OPORY, ne přínos.

## C02 – Kontakt s validací

**Záměr (A i B):**
> Postav stránku „Kontakt“ na `/kontakt` a potvrzovací stránku `/dekujeme`. Cíl: poptávka odeslaná do 2 minut.
> Pocit: klidně, důvěryhodně. Sekce kontaktu: úvod „Ozveme se do 24 h“ (`hero`) a formulář se jménem, e-mailem
> a popisem (`form`) s tlačítkem „Odeslat poptávku“. Formulář rozptýlí obavu ze spamu (stačí e-mail, ozveme se
> jednou). Prázdné jméno, neplatný e-mail nebo popis kratší než 10 znaků formulář neodešle a u pole ukáže chybu;
> platný formulář přejde na `/dekujeme` (sekce `hero` s poděkováním). Odeslání zatím jen na klientovi, bez API.

**Zdrojová data:** kontrakt §3.1 (`/kontakt`, `goal` „Poptávka odeslaná do 2 minut“, `feel` „klidně,
důvěryhodně“, sekce `hero`, `form` s `moves` „Rozptýlí obavu ze spamu: jen e-mail, ozveme se jednou do 24 h.“);
přidaná stránka `dekujeme` (`/dekujeme`, sekce `hero`). Cesta `poptavka`: `s1 /kontakt via open` →
`s2 /dekujeme via {do: submit, section: form, text: "Odeslat poptávku"}`.

**Výchozí repo:** `T0`.

**Očekávané koncové stavy:**
- Routy `/kontakt`, `/dekujeme`; sekce `hero`, `form` na `/kontakt`, `hero` na `/dekujeme`.
- Odeslání prázdného formuláře: URL zůstane `/kontakt`; v `[data-opora-section="form"]` ≥ 1 viditelný prvek
  `[role="alert"]` nebo `aria-live`; prázdná pole mají `aria-invalid="true"`.
- E-mail `neplatny` + ostatní platné → chyba jen u e-mailu, ostatní hodnoty v polích zůstanou.
- Fixture `poptavka/s2` (`Jméno: Jana Testovací`, `E-mail: jana@example.test`, `Popis: Chci upravit zahradu
  za domem.`) → segment projde (pathname `/dekujeme`).
- Pole mají `<label>` (dosažitelné `getByLabel`).

**Proč je těžký:** chybové stavy nejsou v cestě, takže je harness bez explicitního kritéria nevidí; agent je musí
vzít ze záměru a z `card.states`, ne z plánu přehrání.

## C03 – Kampaň Pěstování (cesta přes tři stránky)

**Záměr (A i B):**
> Postav web kampaně „Pěstování“ se třemi stránkami v menu: Pěstování (`/`), Novinky (`/novinky`), Příběh
> (`/pribeh`). Menu je `<nav>` s odkazy „Domů“, „Novinky“, „Příběh“. Hlavní stránka má sekci formuláře (`form`)
> s e-mailem a tlačítkem „Chci video zdarma“, které po platném odeslání vede na `/novinky`, a sekci výzvy (`cta`)
> s odkazem na příběh. Novinky (sekce `hero`, `clanky`) mají kdekoli odkaz na Příběh. Příběh má sekce `hero`
> a `pribeh`. Zákazník: začínající pěstitel na balkoně; na začátku mu rostliny hynou, na konci ví, co dělá.

**Zdrojová data:** cesta `kampan` „Kampaň Pěstování“ přesně podle `test_journey_plan.py` (`KAMPAN`): `s0 nav` →
`s1 home(/) via click "Domů"` → `s2 novinky via submit section=form text="Chci video zdarma"` → `s3 pribeh`
(bez `via` → click v `body`) a odbočka `s4 pribeh after=s1 via click section=cta`. Doplněno pro eval: `actor`
„Začínající pěstitel na balkoně“, `pointA` „Rostliny mu hynou, neví proč.“, `pointB` „Má zelený balkon a ví, co
dělá.“; stránky: `home` (`goal` „Návštěvník nechá e-mail za video zdarma“, `feel` „vlídně“, sekce `form`,
`cta`), `novinky` (`goal` „Přečte si novinku a jde na příběh“, sekce `hero`, `clanky`), `pribeh` (sekce `hero`,
`pribeh`). Živá OPORA: projekt `draft` mapu nemá (graf prázdný), proto zdroj = fixture.

**Výchozí repo:** `T0`.

**Očekávané koncové stavy:**
- Plán (4 segmenty, přesně jako v `test_plan_lists_segments_in_journey_order…`) projde celý:
  `nav` „Domů“ → `/`; submit ve `form` → `/novinky` (fixture `kampan/s2`: `E-mail: pestitel@example.test`);
  z `/novinky` libovolný odkaz → `/pribeh`; z `/` odkaz v `cta` → `/pribeh`.
- 6 sekcí na správných URL; `<nav>` na všech třech stránkách.
- Neplatný e-mail ve `form` neodešle (URL zůstane `/`).

**Proč je těžký:** odbočka `s4` a `nav` jako „krok“ – agent bez plánu snadno udělá menu bez textu „Domů“ nebo
dá výzvu mimo sekci `cta`, a segment pak neprojde, i když stránka „vypadá hotově“.

## C04 – Novinky: archiv s filtrem (rozšíření)

**Záměr (A i B):**
> Na stránku Novinky (`/novinky`) přidej pod články sekci archivu (`archiv`): seznam aspoň 6 starších novinek
> s rokem a přepínač „Vše / 2025 / 2026“, který seznam filtruje bez načtení stránky. Nic dalšího na webu neměň;
> cesta z hlavní stránky přes Novinky na Příběh musí dál fungovat.

**Zdrojová data:** stránka `novinky` z C03 + nová sekce `archiv` (role `content`, `intent` „Starší novinky
s filtrem podle roku“). Cesta `kampan` beze změny.

**Výchozí repo:** `T1`.

**Očekávané koncové stavy:**
- Sekce `archiv` na `/novinky` za sekcí `clanky`; ≥ 6 položek; klik na „2026“ sníží počet viditelných položek
  a všechny viditelné nesou rok 2026; „Vše“ vrátí původní počet; URL pathname beze změny.
- Logika filtru v samostatném souboru s unit testem (≥ 1 nový test v `npm test`).
- Regrese: plán `kampan` (4 segmenty) projde; `git diff --stat` mimo složku Novinek a `App`/router = 0 souborů.

**Proč je těžký:** lehký; měří, jestli varianta A nedělá zbytečné změny (rozklad celé mapy místo jedné sekce).

## C05 – Kampaň: nový krok Kurz a přesnější přechod (úprava cesty)

**Záměr (A i B):**
> Uprav cestu kampaně Pěstování: za Příběh přidej stránku Kurz (`/kurz`, sekce `hero` a `cenik`), kam se jde
> z Příběhu odkazem „Chci celý kurz“ v nové sekci výzvy (`cta`) na konci příběhu. Z Novinek na Příběh se nově
> chodí jen odkazem „Přečíst příběh“ v sekci `clanek` (nová sekce s doporučeným článkem); obecný odkaz na Příběh
> mimo tuto sekci a menu z Novinek odstraň. Ostatní přechody zůstanou.

**Zdrojová data:** cesta `kampan` po úpravě: `s3 pribeh via {click, section: clanek, text: "Přečíst příběh"}`,
nový `s5 kurz after=s3 via {click, section: cta, text: "Chci celý kurz"}`; stránka `novinky` + sekce `clanek`
(content); `pribeh` + sekce `cta`; nová stránka `kurz` (`goal` „Čtenář si prohlédne ceník kurzu“, sekce `hero`,
`cenik`).

**Výchozí repo:** `T1`.

**Očekávané koncové stavy:**
- Nový plán (5 segmentů) projde; segment `s2→s3` má `scope [data-opora-section="clanek"]`.
- Na `/novinky` žádný `a[href="/pribeh"]` mimo `[data-opora-section="clanek"]` a `<nav>`.
- Routa `/kurz` se sekcemi `hero`, `cenik`; `<nav>` dál bez položky Kurz (není v menu) – kontrola počtu odkazů
  v `nav` = 3.

**Proč je těžký:** úprava cesty vyžaduje i **odebrání** odkazu (negativní kritérium) – bez diffu mapy agent
přidává, ale neodebírá.

## C06 – Prodej kurzu (trychtýř s odbočkou)

**Záměr (A i B):**
> Postav prodejní trychtýř kurzu balkonového pěstování pro začínajícího zahrádkáře, kterému rostliny hynou a stydí
> se zeptat; na konci má zelený balkon a ví, co dělá. Stránky: vstupní `/` (sekce `hero` s tlačítkem „Chci video
> zdarma“ vedoucím na `/video`), obsah zdarma `/video` (sekce `hero`, `video`, `form` s e-mailem a tlačítkem
> „Pošlete mi nabídku“, které po odeslání vede na `/nabidka`), prodej `/nabidka` (sekce `hero`, `cenik`, `cta`
> s odkazem na `/upsell` a menším odkazem na levnější doplněk `/miniupsell`), upsell `/upsell` a miniupsell
> `/miniupsell` (každá sekce `hero`). Obava na obsahu zdarma: „zase spam“.

**Zdrojová data:** kontrakt §3.2, cesta `kurz` „Prodej kurzu“: `vstup / via open` → `obsah /video via click
section=hero text="Chci video zdarma"` (`shift` „Zkusí první krok a funguje to.“, `objection` „Zase spam.“) →
`prodej /nabidka via submit section=form text="Pošlete mi nabídku"` → `upsell /upsell via click` → `mini
/miniupsell after=prodej` (bez `via`). `purpose` „Z návštěvníka platící zákazník s upsellem“.

**Výchozí repo:** `T0`.

**Očekávané koncové stavy:**
- 5 rout, sekce podle záměru; plán 4 segmentů projde: `/`→`/video`, `/video` submit → `/nabidka` (fixture
  `kurz/prodej`: `E-mail: zahradkar@example.test`), `/nabidka`→`/upsell` (libovolný odkaz v `body` s
  `href="/upsell"`), `/nabidka`→`/miniupsell` (odbočka).
- `form` na `/video` má text, který reaguje na obavu ze spamu (soudce; programově: v sekci `form` existuje text
  mimo label a tlačítko).
- Build a test exit 0.

**Proč je těžký:** dva výstupy z jedné stránky a kroky bez `via.text` – runner hledá libovolný odkaz na
`expectPath`, takže chybí-li na `/nabidka` byť jeden z odkazů, odbočka tiše neprojde.

## C07 – Poptávka zahrady (cesta + chyba serveru)

**Záměr (A i B):**
> Pro majitele rodinného domu se zanedbanou zahradou postav dvě stránky a potvrzení. Ukázky realizací
> `/realizace` (sekce `hero`, galerie aspoň 6 realizací `galerie`, výzva `cta` s tlačítkem „Chci podobnou
> zahradu“ vedoucím na `/kontakt`). Poptávka `/kontakt` (sekce `hero`, `form`: jméno, e-mail, velikost zahrady
> v m², popis, tlačítko „Odeslat poptávku“). Formulář posílá `POST /api/poptavka` s JSON; během odesílání je
> tlačítko neaktivní s textem „Odesílám…“; když server vrátí chybu, formulář ukáže srozumitelnou chybu a nechá
> vyplněné hodnoty; při úspěchu přejde na `/dekujeme` (sekce `hero`). Zákazník se bojí telefonátů a skrytých
> cen – formulář to musí rozptýlit. Pocit: věcně, bez nátlaku.

**Zdrojová data:** kontrakt §4 (`poptavka` „Poptávka zahrady“, `actor`, `pointA`, `pointB`, krok `kontakt`
s `shift` „Z ‚asi bych měl‘ na ‚chci prohlídku, vím, co to stojí‘“, `objection` „Bojí se, že ho zavalíme
telefonáty a skrytými cenami“); kroky `realizace /realizace via open` → `kontakt /kontakt via click section=cta
text="Chci podobnou zahradu"` → `dik /dekujeme via submit section=form text="Odeslat poptávku"`. Komponenta
formuláře: `out` `command` → `POST /api/poptavka`, `states` prázdno / odesílá / chyba / hotovo (pravidlo
`state.no-error`).

**Výchozí repo:** `T0`.

**Očekávané koncové stavy:**
- Plán 2 segmentů projde se stubem `POST /api/poptavka` → 201 a fixture `poptavka/dik` (fiktivní jméno,
  `zahrada@example.test`, `Velikost: 400`, popis).
- Stub → 500: URL zůstane `/kontakt`, v sekci `form` viditelný `[role="alert"]`, všechna pole drží zadané hodnoty.
- Stub se zpožděním 1 s: během čekání je tlačítko `disabled` a má text „Odesílám…“.
- Tělo požadavku je JSON se 4 klíči (jakékoli názvy), `Content-Type: application/json`.
- Galerie ≥ 6 položek s `alt`.

**Proč je těžký:** kombinuje cestu, síťový `command` a čtyři stavy – a stav „chyba“ je přesně to, co `gaps`
v `node-brief` hlídá a co čistý text záměru snadno zapadne.

## C08 – Ample: zapomenuté heslo

**Záměr (A i B):**
> V aplikaci Ample přidej na přihlašovací stránku (`/login`) pod formulář sekci (`zapomenute-heslo`) s odkazem
> „Zapomněl jsem heslo“, který vede na novou veřejnou stránku `/zapomenute-heslo` (přístupnou bez přihlášení).
> Stránka má sekci `form` s polem e-mail a tlačítkem „Poslat odkaz“; neplatný e-mail ukáže chybu u pole; po
> odeslání (`POST /api/v1/auth/password-reset`, backend zatím neexistuje, neřeš ho) ukáže na stejné stránce
> potvrzení „Pokud účet existuje, poslali jsme odkaz“ bez ohledu na to, zda e-mail existuje. Drž konvence
> repozitáře (feature složka, styl, README).

**Zdrojová data:** živá mapa Ample (`cc5f34ec…`) stránku `/login` nemá (mapa má jen `/organizace`, `/projekty`,
`/tym-opravneni`, `/projects`, `/trenovani` bez sekcí a cílů), proto se do mapy A doplní: stránka `login`
(`/login`, sekce `form`, `zapomenute-heslo`), stránka `zapomenute-heslo` (`goal` „Uživatel si vyžádá obnovu hesla
bez prozrazení, zda účet existuje“, `feel` „klidně“, sekce `form`), cesta `obnova`: `login via open` →
`reset via click section=zapomenute-heslo text="Zapomněl jsem heslo"`.

**Výchozí repo:** `AMP` (stub `GET /api/v1/auth/status` → systém s vlastníkem, nepřihlášen; `POST
/api/v1/auth/password-reset` → 202).

**Očekávané koncové stavy:**
- Segment `/login` → `/zapomenute-heslo` projde; přímé otevření `/zapomenute-heslo` bez cookie **neskončí** na
  `/login` (routa mimo `ProtectedLayout`).
- E-mail `x@` → `aria-invalid` + chyba v sekci `form`, žádný požadavek na API (počítadlo stubu = 0).
- Platný e-mail → 1 požadavek, potvrzující text viditelný, URL beze změny.
- Nová složka `frontend/auth/<něco>-page/` obsahuje `components/`, `logic/` s testem, `styles/`, `README.md`
  (konvence `frontend/CLAUDE.md`); `npm test` – všechny dříve zelené testy zelené.

**Proč je těžký:** existující AuthGate a konvence repozitáře – snadno se stránka zařadí pod chráněnou vrstvu nebo
mimo feature strukturu, a programová kontrola to odhalí.

## C09 – Ample: sekce stránky Projekty + nápověda

**Záměr (A i B):**
> Na vstupní stránce Ample se seznamem projektů (`/`) označ existující části jako sekce: hlavička s názvem
> organizace a tlačítkem Nový projekt (`uvod`), mřížka karet projektů (`projekty`), uvítací karta prázdné
> organizace (`prazdny-stav`). Pod mřížku přidej novou sekci nápovědy (`napoveda`) se dvěma větami a odkazem
> „Nastavení organizace“ na `/settings/organization`. Vzhled existujících částí neměň.

**Zdrojová data:** stránka `projekty` (v živé mapě Ample `eb868222…` s `path=/projects`, ve skutečném routeru je
seznam na `/`; eval bere skutečnou routu `/`), `goal` „Uživatel otevře projekt nebo založí první“, sekce `uvod`
(hero), `projekty` (gallery), `prazdny-stav` (cta), `napoveda` (content). Bez cesty.

**Výchozí repo:** `AMP` (stuby: `auth/status` + `auth/me` → přihlášený vlastník „Testovací Vlastník“,
`organizations` → 1 fiktivní organizace, `projects` → 2 projekty; druhý běh `projects` → `[]`).

**Očekávané koncové stavy:**
- S projekty: sekce `uvod`, `projekty`, `napoveda` viditelné; `prazdny-stav` ne. Bez projektů: `prazdny-stav`
  viditelná.
- `[data-opora-section="napoveda"] a[href="/settings/organization"]` existuje a klik změní pathname na
  `/settings/organization`.
- Screenshot diff hlavičky a mřížky proti výchozímu stavu ≤ 1 % pixelů (mimo nové sekce).
- Všechny dříve zelené testy zelené; `ProjectsPage.tsx` nepřekročí ~200 řádků (pravidlo repa), jinak nová
  komponenta.

**Proč je těžký:** lehký; testuje, zda agent umí sekce **přiřadit k existujícímu kódu** místo psaní nového.

## C10 – Ample: cesta „Přizvat tým“ s chybou pozvánky

**Záměr (A i B):**
> V Ample přidej cestu vlastníka organizace k přizvání kolegů. Na vstupní stránce (`/`) přidej nad mřížku
> projektů sekci (`tym-vyzva`) s větou o spolupráci a odkazem „Přizvat kolegy“ na `/settings/team`. Na stránce
> týmu označ panel pozvánek jako sekci `pozvanky`; když pozvánka na e-mail, který už v organizaci je, skončí
> odpovědí 409, panel ukáže chybu „Tento e-mail už v organizaci je“ u pole a nechá zadaný e-mail; ostatní chyby
> obecnou hlášku. Úspěšná pozvánka se objeví v seznamu bez načtení stránky.

**Zdrojová data:** mapa A: stránky `projekty` (`/`, sekce `tym-vyzva` cta, `projekty`), `tym` (`/settings/team`,
sekce `clenove`, `pozvanky` form, `moves` „Rozptýlí obavu z chybné pozvánky jasnou hláškou“); cesta `prizvat`
„Přizvat tým“ (`actor` „Vlastník malé organizace“, `pointA` „Pracuje v aplikaci sám“, `pointB` „Má v projektu
kolegu s rolí“): `s1 / via open` → `s2 /settings/team via click section=tym-vyzva text="Přizvat kolegy"`.
Skutečný kód: `frontend/settings/team/invitations-panel`, API pozvánek v `backend/api/team_routes.py`.

**Výchozí repo:** `AMP` (stuby `/api/v1/**`: přihlášený vlastník, organizace, členové, pozvánky; `POST` pozvánky
→ 201 pro `novy@example.test`, 409 pro `existujici@example.test`). Přesné cesty endpointů harness vezme z
`api-types`/`team_routes.py` na `7e78d68`.

**Očekávané koncové stavy:**
- Segment `/` → `/settings/team` z `[data-opora-section="tym-vyzva"]` projde.
- 409 → v `[data-opora-section="pozvanky"]` text „Tento e-mail už v organizaci je“, e-mail v poli zůstane, URL beze
  změny; 500 → jiná (obecná) hláška.
- 201 → počet položek seznamu pozvánek +1 bez navigace.
- `tym-vyzva` vidí jen role, které smí zvát (stub role „member“ → sekce chybí nebo odkaz chybí).
- Všechny dříve zelené testy zelené.

**Proč je těžký:** tři existující dílky (ProjectsPage, TeamPage, InvitationsPanel), oprávnění podle role
a rozlišení 409/500 v existujícím klientovi API – nejvíc místa pro regresi.

## C11 – Novinky (jedna stránka)

**Záměr (A i B):**
> Postav stránku „Novinky“ na `/novinky` webu o balkonovém pěstování. Cíl: čtenář najde aktuální tip a pokračuje
> na příběh autorky. Pocit: svěže, prakticky. Sekce: úvod (`hero`), tři karty článků s nadpisem, datem a perexem
> (`clanky`), časté otázky aspoň ve třech rozbalovacích položkách (`faq`), výzva s odkazem „Přečíst příběh“ na
> `/pribeh` (`cta`).

**Zdrojová data:** stránka `novinky` (fixture Pěstování, `/novinky`), `goal` a `feel` podle záměru, sekce `hero`,
`clanky` (gallery), `faq` (faq), `cta` (cta). Bez cesty (jen odkaz).

**Výchozí repo:** `T0`.

**Očekávané koncové stavy:**
- Routa `/novinky`; 4 sekce v pořadí; `clanky` obsahuje 3 `article` s `time[datetime]`.
- `faq` ≥ 3 `details`/`summary` (nebo tlačítka s `aria-expanded`), klik rozbalí obsah.
- `[data-opora-section="cta"] a[href="/pribeh"]` s textem „Přečíst příběh“.

**Proč je těžký:** lehký; druhý kalibrační případ, ověřuje přístupné vzory (`details`, `time`), které nejsou
v mapě, jen v záměru.

## C12 – Prodej kurzu: zrušení odbočky a FAQ proti námitce (úprava cesty)

**Záměr (A i B):**
> Uprav prodejní trychtýř kurzu: levnější doplněk (`/miniupsell`) zrušíme – stránku i všechny odkazy na ni
> odstraň. Na upsell se z prodejní stránky nově jde jen tlačítkem „Přidat konzultaci“ v sekci `cta`. Na stránku
> obsahu zdarma (`/video`) přidej mezi video a formulář sekci častých otázek (`faq`), která rozptýlí obavu „zase
> spam“ (jak často píšeme, jak se odhlásit).

**Zdrojová data:** cesta `kurz` z C06 po úpravě: krok `mini` odebrán; `upsell via {click, section: cta, text:
"Přidat konzultaci"}`; stránka `video` + sekce `faq` (faq, `moves` „Rozptýlí obavu ‚zase spam‘: píšeme jednou
týdně, odhlášení jedním klikem“); stránka `miniupsell` smazána.

**Výchozí repo:** `T2`.

**Očekávané koncové stavy:**
- Nový plán (3 segmenty) projde; segment `prodej→upsell` má `scope [data-opora-section="cta"]` a text
  „Přidat konzultaci“.
- V `src/` žádný literál `/miniupsell` (grep), routa `/miniupsell` vrací fallback/404 stránku.
- Na `/video` pořadí sekcí `hero`, `video`, `faq`, `form`; `faq` ≥ 2 otázky.
- Build/test exit 0 (testy staré odbočky odstraněné nebo upravené, ne přeskočené: žádné `.skip`).

**Proč je těžký:** mazání napříč routerem, odkazy a testy – varianta bez mapy nemá seznam, kde všude krok žil,
a typicky nechá mrtvý odkaz nebo `.skip` test.

---

## Rizika

1. **Pěstování není v živé OPORE.** Projekt `draft` má prázdnou architekturu (`nodes: 0`) a žádný projekt nemá
   cestu „Kampaň Pěstování“; data jsou z `backend/project/architecture/test_journey_plan.py` a
   `docs/brana-cesty.md`. Mapy C01–C07, C11, C12 se musí nasadit do dočasné instance OPORY skriptem (seed).
2. **Šablony `T0`/`T1`/`T2` neexistují.** Je třeba je jednou vytvořit a ručně ověřit, že na `T1`/`T2` projde
   výchozí plán (jinak C04, C05, C12 měří chybu šablony).
3. **Ample v čisté kopii.** Pracovní strom má necommitnuté změny (`backend/…`), proto `git archive 7e78d68`.
   Plný běh potřebuje Python 3.12 + `uv sync`, Redis/Docker (volitelně) a pro journey za AuthGate přihlášení;
   eval proto spouští jen `vite` a **stubuje `/api/v1/**`** v Playwrightu. Riziko: stuby se rozejdou s
   `api-types` → falešné selhání; stuby generovat z typů na `7e78d68` a ověřit na nezměněném Ample (C09/C10
   „před“ musí projít regresní částí).
4. **Ample testy a build trvají.** `npm ci` (~2–4 min bez cache), `vitest run` celé sady a `tsc --noEmit` –
   sdílená cache `node_modules` (kopie, ne symlink, kvůli Windows a cestám s mezerami).
5. **Kontaminace varianty B.** Ample `CLAUDE.md` a README zmiňují OPORA a skill `opora-control-center`; B ho
   nesmí mít nainstalovaný ani mít přístup na `:8740`. Konvenci `data-opora-section` dostávají obě varianty
   v patičce, jinak by eval měřil znalost konvence, ne přínos mapy.
6. **Živá OPORA se nesmí dotknout.** Varianta A potřebuje zápisy (dávka plánu, executions, doklad běhu) – jen
   dočasná instance (`create_app` nad temp data root jako `tools/ab-protokol`), nikdy `:8740` ani `P:\opora-data`.
7. **`journey_run.py`** potřebuje Python Playwright + Chromium (volitelná závislost) a server OPORY pro plán;
   pro harness volat `journey_plan()` přímo a runner v `--dry-run`, ať doklad nejde do žádné OPORY.
8. **Headless Claude Code pod předplatným:** limity zpráv/5 h okno, nedeterminismus (doporučeno ≥ 3 opakování
   na případ a variantu), timeout běhu 60 min; přerušený běh = neúspěch, ne opakování.
9. **Porty a paralelismus na Windows:** každá kopie vlastní port `vite preview` a vlastní instanci OPORY; cesty
   s mezerami (`P:\0. OSVC\…`, `I:\1. Projekty\…`) → pracovní kopie do krátké cesty bez mezer.
10. **Soudce** vidí v diffu A stopy OPORY (komentáře „karta“, `.opora/`) – filtr diffu před párovým soudem,
    jinak není slepý.

## Odhad času na případ (jedna varianta, jeden běh)

| obtížnost | agent | příprava kopie + kontroly (build, test, Playwright) | soudce | celkem |
|---|---|---|---|---|
| lehký (T0) | 8–15 min | 2–3 min | 1 min | ~15 min |
| střední | 20–30 min | 3–5 min (Ample 6–8 min) | 1–2 min | ~30 min |
| těžký | 40–60 min | 4–6 min (Ample 8–10 min) | 2 min | ~55 min |

Varianta A je čekaně o 10–20 % delší (seed mapy, dávka plánu, kontrola mapy). Celá sada: 12 případů × 2
varianty ≈ 4 × 15 + 4 × 30 + 4 × 55 = 400 min na variantu → **~13–14 h sekvenčně na jedno opakování**,
při 4 paralelních kopiích ~3,5 h; se 3 opakováními ~10–11 h paralelně. Jednorázová příprava (šablony T0–T2,
seed skript, stuby Ample, harness kontrol): odhadem 1–1,5 dne.
