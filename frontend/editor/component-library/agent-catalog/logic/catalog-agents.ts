// Kategorie Agenti: role a model, kdo smí co a jak hlásí zpátky. Drop položky vytvoří pravidlo uzlu
// s rolí a modelem — proto hint každé položky nese „role: … · model: …“ napřed.
import type { AgentItem } from "./agent-catalog";

export const agentItems: AgentItem[] = [
  {
    id: "agent-main-thread",
    category: "agents",
    label: "Hlavní vlákno: Fable/Opus",
    hint: "role: hlavní vlákno · model: Fable/Opus — drží celek, čte zadání, píše kontrakt, ověřuje.",
    icon: "◆",
    kind: "agent",
    rules: {
      must: [
        "Hlavní vlákno čte zadání a rozděluje práci na nezávislé kusy.",
        "Hlavní vlákno samo spouští uv run pytest backend, npm test, npm run build — nepřebírá hlášení hotovo naslepo.",
        "Zadání subagentovi obsahuje kontrakt, soubory, ověřovací příkazy a zákaz mimo scope.",
      ],
      mustNot: [
        "Neimplementuje rutinní hledání samo, když se dá delegovat levněji.",
        "Nepotvrzuje done karty (confirmed: true) — to dělá jen člověk.",
      ],
    },
    decomposition: [
      { title: "Čte", text: "Zadání, kontrakt, docs/." },
      { title: "Rozděluje", text: "Nezávislé kusy práce podle kompetence modelu." },
      { title: "Ověřuje", text: "Spouští ověřovací brány, čte diff, neschvaluje naslepo." },
    ],
    template: [
      "1. Přečti zadání a kontrakt (docs/, karta).",
      "2. Rozděl práci na nezávislé kusy podle role a modelu.",
      "3. Zadej subagentovi kontrakt, soubory, ověřovací příkazy a zákaz mimo scope.",
      "4. Po návratu spusť ověření sám.",
      "5. Zapiš log/handoff, navrhni done.",
    ].join("\n"),
    endCriteria: "Práce je rozdělená, subagenti se drželi scope, ověření proběhlo v hlavním vlákně.",
    stopCondition: "Úkol není rozdělitelný nebo kontrakt chybí — napiš kontrakt sám, než cokoli deleguješ.",
    refs: [],
  },
  {
    id: "agent-explore-haiku",
    category: "agents",
    label: "Subagent Explore: haiku",
    hint: "role: hledání a čtení · model: haiku (levný) — najde soubory a symboly, nic nemění.",
    icon: "⌕",
    kind: "agent",
    rules: {
      must: [
        "Explore jen hledá a čte; vrací cesty a řádky se stručným shrnutím.",
        "Explore se používá, když hlavní vlákno neví, kde věc leží, nebo pro širší průzkum.",
      ],
      mustNot: [
        "Explore nezapisuje soubory a neprovádí edity.",
        "Explore se nepoužívá na architektonické rozhodnutí — to zůstává hlavnímu vláknu.",
      ],
    },
    decomposition: [
      { title: "Zadání", text: "Co hledat: vzor, symbol, otázka „kde je X“." },
      { title: "Výsledek", text: "Cesty a řádky, ne celé soubory přepsané do kontextu." },
    ],
    template: [
      "1. Zadej přesný hledaný vzor nebo otázku.",
      "2. Urči šíři hledání (rychlé / střední / důkladné).",
      "3. Přijmi zpět cesty a řádky, ne úsudek o architektuře.",
    ].join("\n"),
    endCriteria: "Hlavní vlákno dostalo přesnou lokaci (cesta a řádek) bez zbytečného balastu v kontextu.",
    stopCondition: "Hledání nic nenašlo ani po důkladném průzkumu — nahlas to hlavnímu vláknu, nevymýšlej umístění.",
    refs: [],
  },
  {
    id: "agent-sonnet-feature",
    category: "agents",
    label: "Subagent Sonnet: data, testy, menší feature",
    hint: "role: menší samostatný kus s testy · model: Sonnet — přesné zadání, soubory, kontrakt.",
    icon: "●",
    kind: "agent",
    rules: {
      must: [
        "Sonnet dostává přesné zadání: kontrakt, seznam souborů, ověřovací příkazy.",
        "Sonnet píše test vedle kódu: nejdřív padající test, pak implementace.",
        "Sonnet hlásí zpět: log (co udělal), failures (co nešlo), fixes (co opravil), handoff (co zbývá).",
      ],
      mustNot: [
        "Sonnet nesahá mimo přidělené soubory nebo scope.",
        "Sonnet nehlásí hotovo bez spuštěného testu.",
      ],
    },
    decomposition: [
      { title: "Zadání", text: "Kontrakt, soubory, testy a zákaz mimo scope." },
      { title: "Práce", text: "Menší feature nebo datová/testovací úloha, test nejdřív." },
      { title: "Hlášení", text: "log/failures/fixes/handoff zpět hlavnímu vláknu." },
    ],
    template: [
      "1. Přečti kontrakt a rozsah souborů.",
      "2. Napiš padající test, pak implementaci.",
      "3. Spusť ověřovací příkazy ze zadání.",
      "4. Zapiš log, failures, fixes, handoff a vrať se.",
    ].join("\n"),
    endCriteria: "Testy ze zadání prochází, hlášení nese log/failures/fixes/handoff.",
    stopCondition: "Zadání chybí kontrakt nebo ověřovací příkazy — zastav a vyžádej si je od hlavního vlákna.",
    refs: [],
  },
  {
    id: "agent-opus-architecture",
    category: "agents",
    label: "Subagent Opus: feature s testy, architektura",
    hint: "role: větší nebo architektonický kus · model: Opus — víc rozhodování, pořád v mezích kontraktu.",
    icon: "◉",
    kind: "agent",
    rules: {
      must: [
        "Opus se nasazuje na feature s víc rozhodováním nebo dotčenou architekturou, ne na prosté hledání.",
        "I Opus dostává kontrakt, soubory a ověřovací příkazy — samostatnost neznamená bez hranic.",
        "Opus hlásí stejně jako Sonnet: log/failures/fixes/handoff, plus zdůvodněná rozhodnutí.",
      ],
      mustNot: [
        "Opus neobchází docs/pravidla-struktury.md kvůli složitosti úkolu.",
        "Opus nezavádí závislost bez souhlasu, ani když je architektonicky pohodlnější.",
      ],
    },
    decomposition: [
      { title: "Kdy", text: "Feature s testy, architektonický dopad, víc neznámých rozhodnutí." },
      { title: "Zadání", text: "Kontrakt o něco volnější, ale pořád explicitní o hranicích." },
      { title: "Hlášení", text: "log/failures/fixes/handoff a zdůvodněná rozhodnutí." },
    ],
    template: [
      "1. Potvrď, že úkol má architektonický dopad (jinak stačí Sonnet).",
      "2. Pracuj v mezích kontraktu a docs/pravidla-struktury.md.",
      "3. Zapiš rozhodnutí i log/failures/fixes/handoff.",
    ].join("\n"),
    endCriteria: "Architektonické rozhodnutí je zdůvodněné a zapsané, testy prochází, hranice scope dodržené.",
    stopCondition: "Rozhodnutí přesahuje zadaný scope (mění cizí kontrakt) — zastav a vrať to hlavnímu vláknu.",
    refs: [],
  },
];
