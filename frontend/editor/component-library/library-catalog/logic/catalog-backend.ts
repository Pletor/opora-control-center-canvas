// Kategorie Backend (blok 5) a Databáze (blok 6) sektoru. Router je tenký, logika bydlí v modulu
// prostředí a test leží vedle něj; schéma má u každé tabulky vlastníka a migrace se dá vrátit.
import type { CatalogItem } from "./library-catalog";

export const backendItems: CatalogItem[] = [
  {
    id: "be-environment-router",
    category: "backend",
    label: "Router prostředí",
    hint: "api/<prostředí>/: přijme, ověří tvar, zavolá modul, vrátí odpověď",
    icon: "⇄",
    kind: "card",
    rules: {
      must: [
        "Router leží jen v backend/api/<prostředí>/.",
        "Router validuje tvar vstupu a hned deleguje do modulu.",
        "Chyba uživateli je česky a bez vnitřních detailů.",
      ],
      mustNot: ["Žádná logika v routeru.", "Žádný přímý přístup do databáze z routeru."],
    },
    decomposition: [
      { title: "Router", text: "Cesta, tvar vstupu, volání modulu, odpověď." },
      { title: "Modul prostředí", text: "Logika: čte a zapisuje, hlídá pravidla." },
      { title: "test_<modul>.py", text: "Test leží vedle modulu, ne ve složce tests/." },
    ],
    template: [
      "# backend/api/editor/library_routes.py",
      "@router.post(\"/api/library/insert\")",
      "def insert(payload: InsertRequest) -> InsertResponse:",
      "    return library.insert(payload.project, payload.item_id, payload.expected_revision)",
    ].join("\n"),
  },
  {
    id: "be-cas-revision",
    category: "backend",
    label: "Revize s CAS",
    hint: "Zápis nese expectedRevision; kolize je 409, neznámá entita 404",
    icon: "⟲",
    kind: "card",
    rules: {
      must: [
        "Každý zápis nese revizi, kterou klient četl.",
        "Neshoda revizí končí 409 s českou hláškou a aktuální revizí.",
        "Revize roste o jedna při každém přijatém zápisu.",
      ],
      mustNot: ["Žádný zápis naslepo bez revize.", "Žádné tiché přepsání cizí změny."],
    },
    decomposition: [
      { title: "Čtení", text: "Vrací obsah i revizi." },
      { title: "Zápis", text: "Porovná revizi, uloží, vrátí novou." },
      { title: "Kolize", text: "409 s aktuálním stavem, aby klient mohl sloučit." },
    ],
    template: [
      "# backend/editor/<modul>/store.py",
      "def save(entity_id: str, data: dict, expected_revision: int) -> dict:",
      "    current = read(entity_id)",
      "    if current is None:",
      "        raise NotFound(\"Záznam neexistuje.\")",
      "    if current[\"revision\"] != expected_revision:",
      "        raise Conflict(\"Záznam se mezitím změnil. Načtěte ho znovu.\")",
      "    return write(entity_id, data, current[\"revision\"] + 1)",
    ].join("\n"),
  },
  {
    id: "be-input-validation",
    category: "backend",
    label: "Validace vstupu na serveru",
    hint: "Tvar, délky, enumy; klient jen pomáhá",
    icon: "✓",
    kind: "block",
    rules: {
      must: [
        "Tvar, délky a povolené hodnoty ověřuje server, i když je ověřil klient.",
        "Neplatný vstup končí 400 s větou, co je špatně.",
        "Limit délky má každé textové pole.",
      ],
      mustNot: ["Žádná důvěra ve vstup z prohlížeče.", "Žádná validace jen typovou anotací."],
    },
    decomposition: [
      { title: "Tvar", text: "Povinná pole a jejich typy." },
      { title: "Meze", text: "Délky textů a povolené hodnoty výčtu." },
      { title: "Hláška", text: "Česká věta pro uživatele, detail jen do logu." },
    ],
    template: [
      "# backend/editor/<modul>/validation.py",
      "SECTIONS = {\"log\", \"failures\", \"fixes\", \"handoff\"}",
      "def check(section: str, text: str) -> str:",
      "    if section not in SECTIONS:",
      "        raise BadRequest(\"Neznámá sekce pracovního prostoru.\")",
      "    return text[:12000]",
    ].join("\n"),
  },
  {
    id: "be-czech-error",
    category: "backend",
    label: "Chyba s českou hláškou",
    hint: "Uživatel čte větu, log čte vývojář",
    icon: "!",
    kind: "block",
    rules: {
      must: [
        "Hláška pro uživatele je česky a říká, co dělat dál.",
        "Technický detail jde do logu, ne do odpovědi.",
        "Stavový kód odpovídá příčině (400 / 404 / 409).",
      ],
      mustNot: ["Žádný stack trace v odpovědi.", "Žádná anglická hláška v uživatelském rozhraní."],
    },
    decomposition: [
      { title: "Typ chyby", text: "BadRequest, NotFound, Conflict — jeden typ na příčinu." },
      { title: "Hláška", text: "Věta pro člověka u každého typu." },
      { title: "Log", text: "Kontext projektu a prostoru ke stopě." },
    ],
    template: [
      "# backend/app/errors.py",
      "class Conflict(Exception):",
      "    status = 409",
      "    def __init__(self, message: str = \"Záznam se mezitím změnil.\") -> None:",
      "        super().__init__(message)",
    ].join("\n"),
  },
  {
    id: "be-module-with-test",
    category: "backend",
    label: "Modul prostředí s testem vedle",
    hint: "Logika mimo router, test_<modul>.py ve stejné složce",
    icon: "▣",
    kind: "card",
    rules: {
      must: [
        "Modul patří do backend/<prostředí>/<oblast>/.",
        "Test se jmenuje test_<modul>.py a leží vedle.",
        "Balíček má README, které říká, co modul vlastní.",
      ],
      mustNot: ["Žádná složka tests/ stranou.", "Žádné sdílení stavu mezi prostředími přes globální proměnné."],
    },
    decomposition: [
      { title: "Modul", text: "Čistá funkce nebo služba nad úložištěm." },
      { title: "Test", text: "Případ užití a hraniční případ." },
      { title: "README", text: "Kdo modul vlastní a co do něj nepatří." },
    ],
    template: [
      "# backend/editor/library/catalog.py",
      "def items_of(category: str) -> list[dict]:",
      "    return [item for item in CATALOG if item[\"category\"] == category]",
      "",
      "# backend/editor/library/test_catalog.py",
      "def test_items_of_vraci_jen_svou_kategorii() -> None:",
      "    assert all(i[\"category\"] == \"backend\" for i in items_of(\"backend\"))",
    ].join("\n"),
  },
];

export const databaseItems: CatalogItem[] = [
  {
    id: "db-table-owner",
    category: "database",
    label: "Tabulka s vlastníkem ve schématu",
    hint: "Vytváření jen ve schématu, u každé tabulky komentář, kdo ji vlastní",
    icon: "▤",
    kind: "card",
    rules: {
      must: [
        "Tabulka vzniká jen ve schématu, nikdy v modulu za běhu.",
        "Komentář u tabulky říká, který modul ji vlastní.",
        "Klíče a cizí klíče jsou pojmenované.",
      ],
      mustNot: ["Žádné CREATE TABLE rozeseté po kódu.", "Žádná tabulka bez vlastníka."],
    },
    decomposition: [
      { title: "Definice", text: "Sloupce, klíče, výchozí hodnoty." },
      { title: "Vlastník", text: "Komentář: který modul do tabulky píše." },
      { title: "Registrace", text: "Tabulka je součástí jednoho schématu projektu." },
    ],
    template: [
      "# database/schema/project_schema.py",
      "# Vlastník: backend/editor/library — katalog vložených položek.",
      "LIBRARY_INSERTS = \"\"\"",
      "CREATE TABLE IF NOT EXISTS library_inserts (",
      "  id TEXT PRIMARY KEY,",
      "  node_id TEXT NOT NULL,",
      "  item_id TEXT NOT NULL,",
      "  created_at TEXT NOT NULL",
      ")",
      "\"\"\"",
    ].join("\n"),
  },
  {
    id: "db-reversible-migration",
    category: "database",
    label: "Vratná a idempotentní migrace",
    hint: "Spustí se dvakrát se stejným výsledkem a umí zpět",
    icon: "⇅",
    kind: "card",
    rules: {
      must: [
        "Migrace je idempotentní (IF NOT EXISTS, kontrola stavu).",
        "Ke každému kroku existuje krok zpět nebo doklad, proč nejde.",
        "Data se před nevratným krokem zálohují.",
      ],
      mustNot: ["Žádná migrace, která maže sloupec bez zálohy.", "Žádný ruční zásah bez záznamu."],
    },
    decomposition: [
      { title: "up()", text: "Přidá tabulku nebo sloupec; dá se spustit opakovaně." },
      { title: "down()", text: "Vrátí změnu do původního stavu." },
      { title: "Ověření", text: "Test na prázdné i naplněné databázi." },
    ],
    template: [
      "# database/migrations/0007_library_inserts.py",
      "def up(db) -> None:",
      "    db.execute(LIBRARY_INSERTS)",
      "",
      "def down(db) -> None:",
      "    db.execute(\"DROP TABLE IF EXISTS library_inserts\")",
    ].join("\n"),
  },
  {
    id: "db-index-by-query",
    category: "database",
    label: "Index podle skutečného dotazu",
    hint: "Index vzniká z dotazu, který je pomalý, ne dopředu",
    icon: "⌗",
    kind: "block",
    rules: {
      must: [
        "Index vzniká až k dotazu, který existuje a je měřitelně pomalý.",
        "Pořadí sloupců indexu kopíruje podmínku dotazu.",
        "U indexu je komentář s dotazem, kvůli kterému vznikl.",
      ],
      mustNot: ["Žádný index „pro jistotu“.", "Žádný index na sloupec s pár hodnotami."],
    },
    decomposition: [
      { title: "Dotaz", text: "Co se ptáme a jak často." },
      { title: "Míra", text: "Kolik řádků dotaz čte bez indexu." },
      { title: "Index", text: "Sloupce v pořadí podmínky." },
    ],
    template: [
      "-- Kvůli: SELECT * FROM library_inserts WHERE node_id = ? ORDER BY created_at DESC",
      "CREATE INDEX IF NOT EXISTS ix_library_inserts_node_created",
      "  ON library_inserts (node_id, created_at DESC);",
    ].join("\n"),
  },
  {
    id: "db-paging",
    category: "database",
    label: "Stránkování velkého výpisu",
    hint: "Velká data po stránkách, agregace v databázi",
    icon: "⋯",
    kind: "card",
    rules: {
      must: [
        "Výpis má limit a kurzor; klient nikdy nedostane vše.",
        "Agregace (count, sum) běží v databázi, ne v aplikaci.",
        "Řazení je stabilní, jinak se stránky překrývají.",
      ],
      mustNot: ["Žádné načtení celé tabulky do paměti.", "Žádné stránkování přes offset u velkých dat."],
    },
    decomposition: [
      { title: "Kurzor", text: "Poslední viděný klíč místo offsetu." },
      { title: "Limit", text: "Pevný strop na stránku." },
      { title: "Součty", text: "Agregace jedním dotazem vedle stránky." },
    ],
    template: [
      "-- stránka po kurzoru, stabilní řazení",
      "SELECT id, node_id, created_at FROM library_inserts",
      "WHERE node_id = :node AND created_at < :cursor",
      "ORDER BY created_at DESC",
      "LIMIT 50;",
    ].join("\n"),
  },
  {
    id: "db-sqlite-limit",
    category: "database",
    label: "Kdy stačí sqlite a kdy ne",
    hint: "Jeden projekt lokálně ano; sdílený zápis po síti ne",
    icon: "◈",
    kind: "block",
    rules: {
      must: [
        "Jeden projekt = jeden soubor databáze ve složce projektu.",
        "Zápis serializovaný; čtení může běžet souběžně.",
        "Přechod dál se rozhoduje podle sdíleného zápisu, ne podle objemu.",
      ],
      mustNot: ["Žádný soubor databáze na síťovém disku.", "Žádný souběžný zápis ze dvou procesů bez zámku."],
    },
    decomposition: [
      { title: "Hranice", text: "Kdy sqlite stačí: lokálně, jeden zapisovatel." },
      { title: "Signál", text: "Co znamená, že je čas přejít dál." },
      { title: "Cesta ven", text: "Schéma připravené na jiný stroj." },
    ],
    template: [
      "# backend/canvas/project_folder.py",
      "def db_path(project_id: str) -> Path:",
      "    return DATA_ROOT / \"projects\" / project_id / \"project.sqlite\"",
    ].join("\n"),
  },
];
