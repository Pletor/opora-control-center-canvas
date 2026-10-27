// Kategorie Backend a Databáze. Router je tenký, logika bydlí v modulu prostředí a test leží vedle
// něj; schéma má u každé tabulky vlastníka a migrace se dá vrátit. Tvar prvku: library-catalog.ts.
import type { CatalogItem } from "./library-catalog";

export const backendItems: CatalogItem[] = [
  {
    id: "be-environment-router",
    category: "backend",
    label: "Router a modul prostředí",
    purpose: "Router v backend/api/<prostředí>/ jen přijme a ověří tvar; logika je v modulu prostředí s testem vedle.",
    relates: [
      "@sec-server-validation",
      "@be-cas-revision",
      "@be-czech-error",
      "@test-unit-beside",
      "Balíček modulu má README, které říká, co vlastní.",
    ],
    done: [
      "Router nemá logiku ani přístup do databáze, jen volá modul.",
      "Vedle modulu leží test_<modul>.py a uv run pytest backend prochází.",
    ],
    invariants: [],
    tech: "FastAPI",
    states: ["přijato", "neplatný vstup", "chyba", "hotovo"],
    ports: [
      { id: "pozadavek", direction: "in", carries: "command" },
      { id: "modul", direction: "out", carries: "command" },
    ],
    fetch: {
      files: ["backend/api/editor/canvas_routes.py", "backend/canvas/canvas_plan.py"],
      docs: ["CLAUDE.md", "docs/pravidla-struktury.md"],
    },
    fill: ["sourceRef", "spec.acceptance"],
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
    purpose: "Zápis nese revizi, kterou klient četl; server zapisuje pod zámkem a při neshodě vrací 409.",
    relates: [
      "@be-environment-router",
      "Desktop v3 stav, uzly grafu i agent-workspace se zapisují s expectedRevision.",
    ],
    done: [
      "Zápis se starou revizí vrátí 409 s aktuální revizí a nic nezapíše.",
      "Přijatý zápis zvýší revizi o jedna.",
    ],
    invariants: [
      { kind: "must", text: "Každý zápis nese očekávanou revizi; zápis bez ní se odmítne." },
      { kind: "must_not", text: "Kolize 409 se nepřepisuje silou; klient načte stav znovu a sloučí." },
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
    id: "be-czech-error",
    category: "backend",
    label: "Chyba s českou hláškou",
    purpose: "Uživatel dostane českou větu, co dělat dál; technický detail jde do logu.",
    relates: ["@cloud-structured-log", "@be-environment-router"],
    done: [
      "Stavový kód odpovídá příčině (400 / 403 / 404 / 409).",
      "Odpověď neobsahuje stack trace ani vnitřní cestu.",
    ],
    invariants: [],
    template: [
      "# backend/app/errors.py",
      "class Conflict(Exception):",
      "    status = 409",
      "    def __init__(self, message: str = \"Záznam se mezitím změnil.\") -> None:",
      "        super().__init__(message)",
    ].join("\n"),
  },
];

export const databaseItems: CatalogItem[] = [
  {
    id: "db-table-owner",
    category: "database",
    label: "Tabulka s vlastníkem ve schématu",
    purpose: "Tabulka vzniká jen ve schématu projektu a komentář u ní říká, který modul do ní píše.",
    relates: ["@db-reversible-migration", "@be-module-boundary"],
    done: [
      "Tabulka je ve schématu s komentářem vlastníka.",
      "V kódu modulů není CREATE TABLE.",
    ],
    invariants: [],
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
    purpose: "Migrace jde spustit dvakrát se stejným výsledkem a má krok zpět.",
    relates: ["@db-table-owner", "@test-fixture-data"],
    done: [
      "up() dvakrát po sobě nehlásí chybu a down() vrátí původní schéma.",
      "Test projde na prázdné i naplněné databázi.",
    ],
    invariants: [{ kind: "must_not", text: "Migrace nemaže sloupec ani tabulku s daty bez zálohy." }],
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
    purpose: "Index vzniká k existujícímu, měřitelně pomalému dotazu a kopíruje pořadí jeho podmínky.",
    relates: ["@db-paging"],
    done: [
      "U indexu je komentář s dotazem, kvůli kterému vznikl.",
      "Plán dotazu (EXPLAIN) index používá.",
    ],
    invariants: [],
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
    purpose: "Velký výpis po stránkách s kurzorem a stabilním řazením; součty počítá databáze.",
    relates: ["@db-index-by-query"],
    done: [
      "Výpis má limit a kurzor, stránky se nepřekrývají.",
      "Agregace běží jedním dotazem v databázi.",
    ],
    invariants: [{ kind: "must_not", text: "Klient nikdy nedostane celou tabulku najednou." }],
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
    purpose: "Jeden projekt lokálně s jedním zapisovatelem stačí sqlite; sdílený zápis po síti už ne.",
    relates: ["@sec-path-guard", "Soubor databáze leží v datové složce projektu."],
    done: ["Rozhodnutí o úložišti je zapsané s důvodem (počet zapisovatelů, síť)."],
    invariants: [{ kind: "must_not", text: "Soubor sqlite nesmí ležet na síťovém disku ani mít dva zapisovatele bez zámku." }],
    template: [
      "# backend/canvas/project_folder.py",
      "def db_path(project_id: str) -> Path:",
      "    return DATA_ROOT / \"projects\" / project_id / \"project.sqlite\"",
    ].join("\n"),
  },
];
