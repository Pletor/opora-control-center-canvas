// Kategorie Security a Testy. Validace vždy na serveru, tajemství nikde v klientu ani v promptu;
// test leží vedle logiky a „hotovo“ je výstup bran, ne dojem. Tvar prvku: library-catalog.ts.
import type { CatalogItem } from "./library-catalog";

export const securityItems: CatalogItem[] = [
  {
    id: "sec-same-origin-write",
    category: "security",
    label: "Same-origin zápis a ochrana proti CSRF",
    purpose: "Server přijme zápis jen s hlavičkou Origin vlastní aplikace.",
    relates: ["@be-environment-router", "Nástroje a agenti zapisují přes stejný původ jako aplikace."],
    done: ["Zápis s cizím nebo chybějícím Origin vrátí 403 (test)."],
    invariants: [
      { kind: "must_not", text: "Zápis nikdy nejde přes GET." },
      { kind: "must_not", text: "CORS nepovoluje libovolný původ." },
    ],
    template: [
      "# backend/app/middleware.py",
      "def check_origin(request) -> None:",
      "    origin = request.headers.get(\"origin\")",
      "    if request.method != \"GET\" and origin not in ALLOWED_ORIGINS:",
      "        raise Forbidden(\"Zápis je povolen jen z aplikace.\")",
    ].join("\n"),
  },
  {
    id: "sec-server-validation",
    category: "security",
    label: "Validace a práva na serveru",
    purpose: "Server ověří tvar, délky, povolené hodnoty i právo u každého volání, i když už to ověřil klient.",
    relates: [
      "@be-environment-router",
      "@fe-form-validated",
      "@be-czech-error",
    ],
    done: [
      "Neplatný vstup vrátí 400 s českou větou, co je špatně.",
      "Každé textové pole má limit délky.",
    ],
    invariants: [
      { kind: "must_not", text: "Server nevěří vstupu ani právu odvozenému z toho, co poslal klient." },
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
    id: "sec-no-secrets",
    category: "security",
    label: "Žádná tajemství v kódu ani v promptu",
    purpose: "Tajemství se čtou z proměnných prostředí; v repozitáři je jen .env.example a podklady pro agenta jdou přes redakci.",
    relates: [
      "@cloud-env-split",
      "@cloud-structured-log",
      "Podklady pro agenta (node-brief, packet) se před vydáním redigují.",
    ],
    done: [
      "V diffu, logu ani exportovaném podkladu není klíč, token ani heslo.",
      "Chybějící povinná proměnná zastaví start s jasnou hláškou.",
    ],
    invariants: [
      { kind: "must_not", text: "Tajemství nikdy není v gitu, promptu, logu, snímku obrazovky ani v prohlížeči." },
    ],
    template: [
      "# backend/editor/agent_packet/redact.py",
      "def redact(text: str) -> str:",
      "    return SECRET_PATTERN.sub(\"[skryto]\", text)",
    ].join("\n"),
  },
  {
    id: "sec-path-guard",
    category: "security",
    label: "Zápis jen do datové složky projektu",
    purpose: "Cesta od klienta se rozvine na absolutní a musí zůstat uvnitř složky projektu.",
    relates: ["@sec-upload-limit", "@db-sqlite-limit"],
    done: ["Cesta s .. nebo mimo kořen vrátí chybu a nic nezapíše (test)."],
    invariants: [{ kind: "must_not", text: "Server nezapisuje mimo datovou složku projektu." }],
    template: [
      "# backend/canvas/project_folder.py",
      "def inside(root: Path, candidate: Path) -> Path:",
      "    target = (root / candidate).resolve()",
      "    if not target.is_relative_to(root.resolve()):",
      "        raise Forbidden(\"Cesta míří mimo složku projektu.\")",
      "    return target",
    ].join("\n"),
  },
  {
    id: "sec-upload-limit",
    category: "security",
    label: "Upload obrázku s limitem a jménem od serveru",
    purpose: "Server přijme jen obrázek do limitu velikosti, typ pozná z obsahu a jméno vygeneruje sám.",
    relates: ["@sec-path-guard", "Obrázky jsou podklady uzlu (materials)."],
    done: [
      "Příliš velký soubor nebo jiný typ vrátí 400.",
      "Uložené jméno nepochází od klienta.",
    ],
    invariants: [{ kind: "must_not", text: "Jméno ani typ souboru se nepřebírá od klienta." }],
    template: [
      "# backend/editor/node/materials.py",
      "MAX_UPLOAD_BYTES = 4 * 1024 * 1024",
      "def store(project: str, node_id: str, data: bytes) -> str:",
      "    if len(data) > MAX_UPLOAD_BYTES:",
      "        raise BadRequest(\"Obrázek je příliš velký.\")",
      "    return write(project, node_id, f\"{stamp()}-{token_hex(4)}.jpg\", data)",
    ].join("\n"),
  },
];

export const testItems: CatalogItem[] = [
  {
    id: "test-unit-beside",
    category: "tests",
    label: "Unit test vedle logiky",
    purpose: "Test leží ve stejné složce jako modul a jmenuje se stejně: <name>.test.ts, test_<modul>.py.",
    relates: ["@fe-pure-model", "@be-environment-router", "@test-fixture-data"],
    done: [
      "Test pokrývá běžný i hraniční případ a npm test / uv run pytest backend prochází.",
      "Test nezávisí na pořadí spuštění.",
    ],
    invariants: [],
    template: [
      "// logic/panel-model.test.ts",
      "import { describe, expect, it } from \"vitest\";",
      "import { setQuery, emptyPanel } from \"./panel-model\";",
      "",
      "describe(\"panel-model\", () => {",
      "  it(\"hledání nemění nic jiného než dotaz\", () => {",
      "    expect(setQuery(emptyPanel(), \"grid\")).toEqual({ open: false, query: \"grid\" });",
      "  });",
      "});",
    ].join("\n"),
  },
  {
    id: "test-e2e-path",
    category: "tests",
    label: "E2e cesta uživatele",
    purpose: "Test projde cestu uživatele proti skutečnému API a každý krok ověří na obrazovce.",
    relates: ["@test-done-gates"],
    done: [
      "Každý krok končí viditelným důkazem (text, prvek, stav).",
      "Test nezávisí na datech konkrétního projektu.",
    ],
    invariants: [],
    template: [
      "// e2e: cesta „vložit položku z knihovny“",
      "1. Otevřít projekt a vrstvu.",
      "2. Otevřít Knihovnu.",
      "3. Přetáhnout prvek na plátno.",
      "4. Ověřit kartu, bloky a pravidla.",
      "5. Ctrl+Z vrátí plátno zpět.",
    ].join("\n"),
  },
  {
    id: "test-fixture-data",
    category: "tests",
    label: "Fixture jako data",
    purpose: "Připravený stav pro test je hotový objekt pojmenovaný podle situace; každý test bere vlastní kopii.",
    relates: ["@test-unit-beside"],
    done: ["Fixture neobsahuje větvení a testy nesdílejí měnitelný stav."],
    invariants: [],
    template: [
      "// logic/fixtures.ts",
      "export const prazdnaVrstva = () => ({ nodes: [], edges: [] });",
      "export const jednaKarta = () => ({ nodes: [{ id: \"a\", parentId: null }], edges: [] });",
    ].join("\n"),
  },
  {
    id: "test-done-gates",
    category: "tests",
    label: "Brány hotovo",
    purpose: "Před hlášením hotovo proběhnou uv run pytest backend, npm test a npm run build a výstup je v hlášení.",
    relates: ["@test-unit-beside", "@test-e2e-path"],
    done: [
      "Všechny tři příkazy prošly a jejich výstup je v hlášení.",
      "Co spustit nešlo, je v hlášení jmenovitě s důvodem.",
    ],
    invariants: [{ kind: "must_not", text: "Hotovo se nehlásí, když některá brána selhala." }],
    template: [
      "uv run pytest backend",
      "npm test",
      "npm run build",
    ].join("\n"),
  },
];
