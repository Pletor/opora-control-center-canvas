// Kategorie Skills: kdy sáhnout po instalovaném skillu, podle jeho popisu (`description`), ne podle
// volné asociace na jméno. `kind: "info"` — položka se na plátno netáhne, je to jen orientace.
import type { AgentItem } from "./agent-catalog";

export const skillItems: AgentItem[] = [
  {
    id: "skill-opora-control-center",
    category: "skills",
    label: "opora-control-center: obsluha aplikace",
    hint: "Ovládá OPORA Canvas: uzly, sektory, podklady pro agenta, mapy a telemetrii — ne obecné programování.",
    icon: "◍",
    kind: "info",
    rules: {
      must: [
        "Použij při práci v projektu / canvasu / uzlu / sektoru / zadání / podkladech / Live Run / API OPORA.",
      ],
      mustNot: [
        "Neaktivuj pro nesouvisející programování nebo obecnou diskusi o filozofii OPORA.",
      ],
    },
    decomposition: [
      { title: "Rozhodni", text: "Obsluha aplikace, nebo změna jejího zdrojového kódu?" },
      { title: "Načti referenci", text: "Jen tu, kterou požadavek potřebuje (navigation / editor / external-agent / live-run / archify / graphify / map-refresh / api / bugfix / source-map)." },
    ],
    template: [
      "1. Rozliš obsluhu aplikace od změny kódu.",
      "2. Zjisti adresu běžící instance.",
      "3. Spusť pomocný skript (nečti ho, jen při jeho opravě).",
      "4. Načti jen referenci pro daný požadavek.",
    ].join("\n"),
    endCriteria: "Úkol se vyřešil zavoláním správné reference nebo skriptu, ne čtením celé složky skillu.",
    stopCondition: "Úkol je obecné programování mimo OPORA aplikaci — tento skill nepoužívej.",
    refs: [],
  },
  {
    id: "skill-prompt-master",
    category: "skills",
    label: "prompt-master: psaní promptu pro konkrétní nástroj",
    hint: "Jen když uživatel výslovně žádá napsat, opravit nebo vylepšit prompt pro pojmenovaný AI nástroj.",
    icon: "✎",
    kind: "info",
    rules: {
      must: [
        "Aktivuj jen na výslovnou žádost o prompt pro pojmenovaný nástroj (LLM, Cursor, Midjourney, video AI, coding agent…).",
      ],
      mustNot: [
        "Neaktivuj pro běžné programování, psaní dokumentů nebo obecnou konverzaci.",
        "Nezobrazovat jména frameworků v samotném výstupu promptu.",
      ],
    },
    decomposition: [
      { title: "Cíl", text: "Urči cílový nástroj; při nejasnosti se zeptej." },
      { title: "Jádro", text: "Vytáhni skutečný záměr ze zadání, ne jen povrch žádosti." },
      { title: "Výstup", text: "Jeden hotový prompt k vložení, bez zbytečných vysvětlivek." },
    ],
    template: [
      "1. Potvrď cílový nástroj.",
      "2. Vytáhni záměr, ne povrch žádosti.",
      "3. Vrať jeden production-ready prompt.",
    ].join("\n"),
    endCriteria: "Vrácen jeden prompt pro potvrzený nástroj, bez teorie promptování navíc.",
    stopCondition: "Cílový nástroj není jasný — zeptej se (nejvýš třikrát), nedomýšlej ho.",
    refs: [],
  },
  {
    id: "skill-graphify",
    category: "skills",
    label: "graphify: kód a dokumenty jako gráf znalostí",
    hint: "Jakýkoli vstup na perzistentní gráf; dotaz na architekturu jde přes graphify-out/ jako první krok.",
    icon: "⌬",
    kind: "info",
    rules: {
      must: [
        "Když existuje graphify-out/, otázku o kódu, architektuře nebo vztazích souborů řeš přes graphify jako první krok.",
      ],
      mustNot: [
        "Nevymýšlet vztahy v kódu, které graphify-out/GRAPH_REPORT.md nepotvrzuje, když je dostupný.",
      ],
    },
    decomposition: [
      { title: "Dostupnost", text: "context.knowledgeGraph.available z node-brief řekne, jestli mapa existuje." },
      { title: "Dotaz", text: "query/path/explain nad grafem místo ručního prohledávání celého repa." },
      { title: "Využití", text: "Souvislosti v kódu, které karty samy nenesou." },
    ],
    template: [
      "1. Zkontroluj context.knowledgeGraph.available v node-brief.",
      "2. Pokud true, polož dotaz nad graphify-out/graph.json.",
      "3. Souvislosti z grafu použij jako doplněk ke kartě, ne jako náhradu.",
    ].join("\n"),
    endCriteria: "Otázka o architektuře nebo vztazích byla zodpovězena z grafu, když byl dostupný.",
    stopCondition: "Graf není vygenerovaný a otázka na něm závisí — řekni to a nabídni vygenerování, nedomýšlej strukturu.",
    refs: [],
  },
  {
    id: "skill-selection-general",
    category: "skills",
    label: "Kdy sáhnout po skillu obecně",
    hint: "Skill se volá, když popis přesně sedí na úkol, jinak pokračuje běžný postup bez skillu.",
    icon: "✺",
    kind: "info",
    rules: {
      must: [
        "Skill se aktivuje podle přesného zacílení v jeho popisu (description), ne podle volné asociace.",
      ],
      mustNot: [
        "Nevolat skill proaktivně mimo jeho popsané spouštěče.",
        "Nekombinovat dva skilly nad stejným krokem bez důvodu.",
      ],
    },
    decomposition: [
      { title: "Popis", text: "Přečti description skillu, ne jen jméno." },
      { title: "Shoda", text: "Sedí aktuální úkol přesně na jeho spouštěč?" },
      { title: "Jinak", text: "Pokračuj běžným postupem bez skillu." },
    ],
    template: [
      "1. Přečti description kandidátního skillu.",
      "2. Ověř, že úkol sedí na jeho spouštěč.",
      "3. Pokud ano, načti skill; pokud ne, pokračuj bez něj.",
    ].join("\n"),
    endCriteria: "Zvolený skill (nebo jeho vynechání) odpovídá jeho popsanému spouštěči.",
    stopCondition: "Dva skilly si konkurují o stejný úkol — zastav a vyber podle přesnosti popisu, ne náhodně.",
    refs: [],
  },
];
