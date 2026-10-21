# Skutečný provozní průchod OporaHubu — 2026-10-21

Průchod použil skutečné Managed Agents API a soukromý GitHub repozitář,
publikovaný Office produktový commit `bc25ebb` a čerstvý oddělený Canvas se stejným
produktovým kódem jako `ee78711`. [Sanitizovaný záznam](oporahub-live-staging-evidence.json)
uchovává přesné identity, piny, výsledek, kumulativní usage a hashe nástrojových událostí.
Neobsahuje klíče, soukromé lease, obsah repozitáře ani raw provider odpovědi.

| Skutečný běh | Výsledek | Ukončení | Ceníková spotřeba |
|---|---|---|---|
| Context v1, původní adaptér | Negativní případ: chyba provider query, 0 native receipt; bez náhrady a zpětného odeslání | Provider potvrdil `terminated`, autorita odebrána | 1 USD cent / 15,71 aktivní sekundy |
| Context v2 / budget v2, opravený adaptér | Pozitivní případ: právě 1 native receipt a přesný sedmipolový context proof | Provider potvrdil `terminated`, autorita odebrána | 2 USD centy / 25,12 aktivní sekundy |

Celkem byly vytvořeny právě dvě povolené sessions, obě ukončené. Ceníková spotřeba
činí 3 USD centy; není to faktura ani důkaz přesného peněžního hard capu.
Samostatné syntetické HTTP kontroly obou kontextových verzí zůstávají odlišným důkazem.
Není tvrzeno, že oba živé běhy skončily úspěšným odevzdáním.

## Ověřený řetězec

1. Server vytvořil testovací karty a přijal jejich zadání i obsah nativními
   neměnnými návrhy. Oprava testovací cesty před claimem vytvořila další přijatou
   revizi; historie se nepřepisovala. Každá karta měla budget v2, pevný konec
   300 sekund, omezené pokusy a 100centový ceníkový session strop.
2. Office ověřil agentovu verzi a skutečnou konfiguraci prostředí. Použil Haiku
   4.5, cloudový kontejner, omezenou síť s pěti GitHub hosty a pouze bash.
   Delegování, MCP, skills a instalace balíčků byly vypnuté. Provider/GitHub klíče
   nebyly předány Canvasu ani zadání agenta.
3. Skutečný `publishedRepository` připnul soukromý repozitář na commit
   `ee7871178000bfb371b5f8bf1e3b1a4d16f036f2`, dostupný v origin tracking ref.
   Agent pracoval v odděleném Linux prostředí. Četl nejvýše 16 KiB README a
   vytvořil drobný probe soubor mimo checkout; do repozitáře nezapisoval.
4. Providerem doručené výstupy sedmi úspěšných bash operací druhého běhu
   potvrdily očekávaný commit, Linux a povolenou probe cestu. Nešlo jen o text
   příkazů nebo tvrzení v závěrečné zprávě. Pro tento audit stačila jedna stránka
   událostí (33 záznamů, bez další stránky).
5. Canvas přijal právě jeden výsledek druhého běhu se správným intentem,
   execution, epochou, přijatou revizí a assignment digestem. Výsledek má stále
   důvěru `agent-reported`; nepřijal plán, neověřil automaticky kód ani nedokončil kartu.
6. Nezávislý observer podepsal skutečná kumulativní API čtení. Po receipt následovalo
   ukončení a readback `terminated`; pozdější reconcile i opakovaný start zachovaly
   původní session a receipt. Nový běh ani další výsledek nevznikl.

## Co odhalil první běh

Provider odmítl filtr `types=agent.message` HTTP 400 a uvedl požadovaný parametr
`types[]`. Přímý čtecí dotaz s `types%5B%5D=agent.message` vrátil 200. Adaptér
byl opraven v emitovaném dotazu i allowlistu; HTTP regrese nejprve selhala a
potom prošla. Agent navíc vrátil zprávu v celém `json` Markdown bloku.

Normalizace nyní dovolí pouze celý takový blok nebo raw JSON. Nevybírá JSON
z okolní prózy, jiných jazyků či více bloků. Původní limit bajtů, zákaz duplicit,
kontroly hloubky, konečných čísel a přesné identity zůstávají. Regrese výslovně
ověřuje, že pozdní fenced zpráva ukončeného běhu nevytvoří receipt.
První výsledek se po opravě zpětně neodesílal.

## Rozsah závěru

Toto je omezený provozní důkaz funkčního propojení, připnutí konfigurace,
cloudového vykonávání, výsledku, ukončení a podepsané spotřeby. Není to audit
zabezpečení infrastruktury Anthropic, důkaz přesného fyzického termination SLA,
faktura ani formální důkaz implementace. Síťová pravidla dokládá provider readback;
nebyl prováděn penetrační test firewallu. Lean runtime nebyl součástí průchodu.

Původní soukromé journaly a data zůstaly zachované. Po ukončení obou sessions byl
vlastní zapisovatelný testovací server zastaven a jeho data zkopírována pro
read-only vizuální náhled. Produkce, globální ochrany, merge ani nasazení se neměnily.
