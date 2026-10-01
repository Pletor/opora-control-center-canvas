// Jediná kreslicí sada aplikace: jméno ikony → data cesty na plátně 24×24. Tvary jsou obkreslené
// ze sady Lucide (licence ISC) a vložené ručně jen pro ikony, které rozhraní opravdu používá —
// žádná závislost navíc, žádné písmo s glyfy, žádný stažený balík. Všechno je jedna `d` (víc
// podcest v jedné `d` je v pořádku), protože dílek `Icon` kreslí právě jeden `<path>`.
//
// Proč vůbec: Unicode glyfy (▦ ¶ ⌘) se v každém systému kreslí jinou tloušťkou, jinou velikostí a
// leckde chybí úplně. Lineární sada drží stejnou stopu (1.75px) i stejnou optiku napříč lištou
// módů, Knihovnou i policí Agentů, takže panely vypadají jako jedna aplikace.
//
// Mapování „id kategorie / módu → jméno ikony“ sem nepatří; to zůstává v `logic/` každého panelu
// (`modeIcon`, `categoryIcon`). Tenhle soubor jen ví, jak se která ikona kreslí.

/** Jména ikon, která smí rozhraní použít. Nová ikona = nový řádek tady a cesta v `ICON_PATHS`. */
export type IconName =
  // Módy plátna a Knihovna (lišta módů)
  | "layout-grid"
  | "type"
  | "pencil"
  | "map"
  | "bot"
  | "library"
  // Kategorie bloků (Knihovna)
  | "component"
  | "function-square"
  | "palette"
  | "server"
  | "database"
  | "refresh-cw"
  | "shield"
  | "cloud"
  | "check-circle"
  // Kategorie postupů (Agenti a postupy)
  | "workflow"
  | "link"
  | "scale"
  | "terminal"
  | "sparkles"
  | "users"
  // Sekce zadání karty
  | "target"
  | "cpu"
  | "repeat"
  | "arrow-left-right"
  | "folder"
  // Stav a směr uvnitř zadání karty
  | "circle"
  | "check"
  | "arrow-up"
  | "arrow-left"
  | "arrow-right"
  // Ovládání panelů
  | "search"
  | "chevron-left"
  | "chevron-right"
  | "panel-left-close"
  | "panel-left-open"
  | "panel-right-close"
  | "panel-right-open"
  | "grip-vertical"
  | "home"
  // Horní lišta: zavěšené panely a jejich zavření
  | "x"
  | "chevron-down"
  // Souhrn práce agentů (mód Text): stav, komunikace, zámek, filtr a řazení
  | "user"
  | "lock"
  | "hourglass"
  | "circle-help"
  | "mail"
  | "play"
  | "filter"
  | "arrow-up-down";

/** Cesta každé ikony na plátně 24×24, stopa zvenčí (`stroke`), nikdy výplň. */
export const ICON_PATHS: Record<IconName, string> = {
  // — Módy plátna a Knihovna —
  /** Struktura: čtyři dlaždice = plátno rozdělené na karty. */
  "layout-grid":
    "M4 3h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M15 3h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M4 14h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1z M15 14h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1z",
  /** Text: serifové „T“ — mód psaní. */
  type: "M4 7V4h16v3 M9 20h6 M12 4v16",
  /** Kreslení: tužka. */
  pencil:
    "M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z M15 5l4 4",
  /** Mapa: složená mapa se třemi lomy. */
  map: "M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z M15 5.764v15 M9 3.236v15",
  /** Agenti: hlava robota s anténou. */
  bot: "M12 8V4H8 M6 8h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2z M2 14h2 M20 14h2 M15 13v2 M9 13v2",
  /** Knihovna: hřbety knih v polici. */
  library: "M16 6l4 14 M12 6v14 M8 8v12 M4 4v16",

  // — Kategorie bloků (Knihovna) —
  /** Komponenty frontendu: čtyři kosočtverce, které do sebe zapadají. */
  component: "M5.5 8.5 9 12l-3.5 3.5L2 12z M12 2l3.5 3.5L12 9 8.5 5.5z M18 8.5l3.5 3.5-3.5 3.5L14.5 12z M12 15l3.5 3.5-3.5 3.5-3.5-3.5z",
  /** Logika frontendu: „f(x)“ v rámečku — funkce. */
  "function-square":
    "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M9 17c2 0 2.8-1 2.8-2.8V10c0-2 1-3.3 3.2-3 M9 11.2h5.7",
  /** CSS: paleta s barvami. */
  palette:
    "M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z M13 6.5a.5 .5 0 1 0 1 0a.5 .5 0 1 0-1 0 M17 10.5a.5 .5 0 1 0 1 0a.5 .5 0 1 0-1 0 M6 12.5a.5 .5 0 1 0 1 0a.5 .5 0 1 0-1 0 M8 7.5a.5 .5 0 1 0 1 0a.5 .5 0 1 0-1 0",
  /** Backend: dva servery nad sebou. */
  server:
    "M4 2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z M4 14h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2z M6 6h.01 M6 18h.01",
  /** Databáze: válec. */
  database: "M3 5a9 3 0 1 0 18 0a9 3 0 1 0-18 0 M3 5v14a9 3 0 0 0 18 0V5 M3 12a9 3 0 0 0 18 0",
  /** Cache: kruh se šipkami — obnovuje se. */
  "refresh-cw": "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8 M21 3v5h-5 M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16 M8 16H3v5",
  /** Bezpečnost: štít. */
  shield:
    "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
  /** Cloud: obláček. */
  cloud: "M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9z",
  /** Testy: fajfka v kolečku. */
  "check-circle": "M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0 M9 12l2 2 4-4",

  // — Kategorie postupů (Agenti a postupy) —
  /** Workflows: dva kroky spojené odbočkou. */
  workflow:
    "M5 3h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M7 11v4a2 2 0 0 0 2 2h4 M15 13h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2z",
  /** Pipelines: dva články řetězu — jedno zapadá do druhého. */
  link: "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71 M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
  /** Pravidla: váhy — co se čím poměřuje. */
  scale:
    "M16 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z M2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z M7 21h10 M12 3v18 M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2",
  /** Hooky a commands: příkazová řádka. */
  terminal: "M4 17l6-6-6-6 M12 19h8",
  /** Skills: jiskry. */
  sparkles:
    "M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z M20 3v4 M22 5h-4 M4 17v2 M5 18H3",
  /** Agenti: dvě postavy — kdo pracuje. */
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M5 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",

  // — Sekce zadání karty —
  /** Cíl a konec: terč. */
  target: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0 M6 12a6 6 0 1 0 12 0a6 6 0 1 0-12 0 M10 12a2 2 0 1 0 4 0a2 2 0 1 0-4 0",
  /** Harness: čip — čím se to má udělat. */
  cpu: "M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z M9 8h6a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z M12 2v2 M17 2v2 M7 2v2 M12 20v2 M17 20v2 M7 20v2 M2 7h2 M2 12h2 M2 17h2 M20 7h2 M20 12h2 M20 17h2",
  /** Smyčka: kolečko, které se vrací na začátek. */
  repeat: "M17 2l4 4-4 4 M3 11v-1a4 4 0 0 1 4-4h14 M7 22l-4-4 4-4 M21 13v1a4 4 0 0 1-4 4H3",
  /** Předávky: šipky tam a zpátky. */
  "arrow-left-right": "M8 3L4 7l4 4 M4 7h16 M16 21l4-4-4-4 M20 17H4",
  /** Pracovní prostor: složka. */
  folder:
    "M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z",

  // — Stav a směr uvnitř zadání karty —
  /** Nesplněno: prázdné kolečko. Je to obraz stavu, ne zaškrtávátko — proto kruh, ne čtvereček. */
  circle: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0",
  /** Splněno: fajfka bez rámečku, aby hotová řádka ztichla a oko sklouzlo na to, co zbývá. */
  check: "M20 6L9 17l-5-5",
  /** Rodičovská karta: šipka nahoru — předávka přichází o vrstvu výš. */
  "arrow-up": "M12 19V5 M5 12l7-7 7 7",
  /** Příchozí předávka: šipka doleva — soused ji poslal sem. */
  "arrow-left": "M19 12H5 M12 19l-7-7 7-7",
  /** Odchozí předávka: šipka doprava — odsud jde dál. */
  "arrow-right": "M5 12h14 M12 5l7 7-7 7",

  // — Ovládání panelů —
  /** Hledání: lupa. */
  search: "M3 11a8 8 0 1 0 16 0a8 8 0 1 0-16 0 M21 21l-4.3-4.3",
  /** Šipka doleva: zavřená kategorie, krok zpět. */
  "chevron-left": "M15 18l-6-6 6-6",
  /** Šipka doprava: otevřená kategorie, krok vpřed. */
  "chevron-right": "M9 18l6-6-6-6",
  /** Sbalit levý panel do hrany. */
  "panel-left-close": "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M9 3v18 M16 15l-3-3 3-3",
  /** Rozbalit levý panel z hrany. */
  "panel-left-open": "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M9 3v18 M14 9l3 3-3 3",
  /** Sbalit pravý panel do hrany. */
  "panel-right-close": "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M15 3v18 M8 9l3 3-3 3",
  /** Rozbalit pravý panel z hrany. */
  "panel-right-open": "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M15 3v18 M10 15l-3-3 3-3",
  /** Úchyt: šest teček — „chyť mě a táhni“. */
  "grip-vertical":
    "M8 5a1 1 0 1 0 2 0a1 1 0 1 0-2 0 M8 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0 M8 19a1 1 0 1 0 2 0a1 1 0 1 0-2 0 M14 5a1 1 0 1 0 2 0a1 1 0 1 0-2 0 M14 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0 M14 19a1 1 0 1 0 2 0a1 1 0 1 0-2 0",
  /** Domeček: kořen stromu stránky. */
  home: "M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8 M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  /** Křížek: zavřít zavěšený panel. */
  x: "M18 6 6 18 M6 6l12 12",
  /** Šipka dolů: rozbalená kapitola, otevřené menu. */
  "chevron-down": "M6 9l6 6 6-6",
  /** Postava: na kartě naposledy psal člověk. */
  user: "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2 M12 3a4 4 0 1 0 0 8a4 4 0 1 0 0-8",
  /** Zámek: karta je uzavřená nebo main je jen ke čtení. */
  lock: "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z M7 11V7a5 5 0 0 1 10 0v4",
  /** Přesýpací hodiny: zpráva čeká na potvrzení příjmu. */
  hourglass:
    "M5 22h14 M5 2h14 M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22 M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2",
  /** Otazník v kruhu: zpráva potřebuje upřesnit. */
  "circle-help": "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20 M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3 M12 17h.01",
  /** Obálka: otevřená otázka v komunikaci. */
  mail: "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z M22 7l-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7",
  /** Trojúhelník: pokračovat dalším krokem. */
  play: "M6 3l14 9-14 9V3z",
  /** Trychtýř: filtr souhrnu. */
  filter: "M22 3H2l8 9.46V19l4 2v-8.54L22 3z",
  /** Dvě šipky proti sobě: řazení. */
  "arrow-up-down": "M21 16l-4 4-4-4 M17 20V4 M3 8l4-4 4 4 M7 4v16",
};

/**
 * Cesta k jménu ikony. Neznámé jméno (cizí data, překlep, starší uložený stav) vrací prázdný
 * řetězec — dílek pak nekreslí nic a rozhraní se kvůli ikoně nikdy nerozbije.
 */
export function iconPath(name: string): string {
  return (ICON_PATHS as Record<string, string>)[name] ?? "";
}
