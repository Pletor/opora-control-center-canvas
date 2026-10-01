// Kategorie Security (blok 9) a Testy (blok 10) sektoru. Validace vždy na serveru, tajemství nikde
// v klientu ani v promptu; test leží vedle logiky a „hotovo“ je výstup tří příkazů, ne dojem.
import type { CatalogItem } from "./library-catalog";

export const securityItems: CatalogItem[] = [
  {
    id: "sec-same-origin-write",
    category: "security",
    label: "Same-origin zápis a ochrana proti CSRF",
    hint: "Zápis přijímáme jen ze své vlastní stránky",
    icon: "⛨",
    kind: "card",
    rules: {
      must: [
        "Každý zápis ověří hlavičku Origin proti vlastní adrese.",
        "Chybějící nebo cizí Origin končí odmítnutím.",
        "Čtení a zápis mají oddělené cesty.",
      ],
      mustNot: ["Žádný zápis přes GET.", "Žádné povolení libovolného původu v CORS."],
    },
    decomposition: [
      { title: "Kontrola", text: "Middleware porovná Origin s vlastní adresou." },
      { title: "Odmítnutí", text: "403 s českou hláškou, bez detailu." },
      { title: "Výjimky", text: "Žádné; nástroje volají přes vlastní původ." },
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
    label: "Validace vždy na serveru",
    hint: "Klient pomáhá uživateli, rozhoduje server",
    icon: "✓",
    kind: "block",
    rules: {
      must: [
        "Server ověří vstup i tehdy, když ho ověřil klient.",
        "Práva se vyhodnocují na serveru u každého volání.",
        "Odmítnutí má stejnou podobu pro všechny cesty.",
      ],
      mustNot: ["Žádné právo odvozené jen z toho, co poslal klient.", "Žádné skryté pole jako nosič práva."],
    },
    decomposition: [
      { title: "Tvar", text: "Povinná pole a typy." },
      { title: "Právo", text: "Smí tento uživatel tuto operaci?" },
      { title: "Odpověď", text: "400 / 403 s větou pro člověka." },
    ],
    template: [
      "# backend/api/editor/node_routes.py",
      "def save(payload: SaveRequest, user: User) -> Response:",
      "    guard(user, \"editor.write\")",
      "    return node.save(check(payload))",
    ].join("\n"),
  },
  {
    id: "sec-no-secrets",
    category: "security",
    label: "Žádná tajemství v kódu ani v promptu",
    hint: "Klíče žijí v proměnných prostředí, ne v repozitáři",
    icon: "⚿",
    kind: "block",
    rules: {
      must: [
        "Tajemství se čte z proměnné prostředí za běhu.",
        "Podklady pro agenta jsou data, ne příkazy, a jdou přes redakci.",
        "Hláška ani log tajemství neopakují.",
      ],
      mustNot: ["Žádný klíč v gitu, v promptu ani ve snímku obrazovky.", "Žádné tajemství posílané do prohlížeče."],
    },
    decomposition: [
      { title: "Zdroj", text: "Proměnná prostředí, načtená jednou." },
      { title: "Redakce", text: "Před odesláním se citlivé části zakryjí." },
      { title: "Kontrola", text: "Test hlídá, že výstup tajemství neobsahuje." },
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
    hint: "Cesta se normalizuje a musí zůstat uvnitř složky projektu",
    icon: "⌂",
    kind: "card",
    rules: {
      must: [
        "Cesta se rozvine na absolutní a porovná s kořenem projektu.",
        "Cesta mimo kořen končí chybou, ne zápisem.",
        "Jméno souboru vzniká na serveru.",
      ],
      mustNot: ["Žádné .. v cestě od klienta.", "Žádný zápis mimo datovou složku projektu."],
    },
    decomposition: [
      { title: "Kořen", text: "Datová složka projektu jako jediné povolené místo." },
      { title: "Normalizace", text: "resolve() a kontrola prefixu." },
      { title: "Chyba", text: "Česká hláška bez vypsání cesty." },
    ],
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
    hint: "Jen obrázky, jen do limitu, jméno generuje server",
    icon: "▣",
    kind: "card",
    rules: {
      must: [
        "Typ souboru se ověří z obsahu, ne z přípony.",
        "Velikost má pevný strop a překročení končí chybou.",
        "Jméno souboru generuje server (čas + náhodný podpis).",
      ],
      mustNot: ["Žádné přebírání jména od klienta.", "Žádný jiný typ než povolené obrázky."],
    },
    decomposition: [
      { title: "Typ", text: "Kontrola hlavičky obsahu." },
      { title: "Limit", text: "Strop velikosti a jasná hláška." },
      { title: "Jméno", text: "Server pojmenuje soubor a vrátí jen relativní cestu." },
    ],
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
    hint: "Stejná složka, stejné jméno: <name>.ts a <name>.test.ts",
    icon: "✓",
    kind: "card",
    rules: {
      must: [
        "Test leží ve stejné složce jako modul a jmenuje se stejně.",
        "Jeden test popisuje jedno chování česky.",
        "Testuje se čistá funkce, ne komponenta.",
      ],
      mustNot: ["Žádná složka tests/ stranou od kódu.", "Žádný test závislý na pořadí spuštění."],
    },
    decomposition: [
      { title: "Případ užití", text: "Co má funkce dělat, když je vše v pořádku." },
      { title: "Hraniční případ", text: "Prázdný vstup, kolize, mimo rozsah." },
      { title: "Doklad", text: "npm test běží bez DOM." },
    ],
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
    hint: "Otevřít projekt, vložit, uložit, vrátit se",
    icon: "➤",
    kind: "card",
    rules: {
      must: [
        "Test jde po cestě uživatele, ne po funkcích.",
        "Každý krok končí viditelným důkazem na obrazovce.",
        "Test běží proti skutečnému API, ne proti atrapě.",
      ],
      mustNot: ["Žádné klikání podle indexů v DOM.", "Žádná závislost na datech konkrétního projektu."],
    },
    decomposition: [
      { title: "Otevřít", text: "Projekt a vrstva." },
      { title: "Změnit", text: "Vložení položky a uložení." },
      { title: "Vrátit", text: "Krok zpět vrátí plátno do původního stavu." },
    ],
    template: [
      "// e2e: cesta „vložit položku z knihovny“",
      "1. Otevřít projekt a vrstvu.",
      "2. Otevřít knihovnu v levé liště.",
      "3. Přetáhnout dlaždici na plátno.",
      "4. Ověřit kartu i bloky rozpadu.",
      "5. Ctrl+Z vrátí plátno zpět.",
    ].join("\n"),
  },
  {
    id: "test-fixture-data",
    category: "tests",
    label: "Fixture jako data",
    hint: "Připravený stav je objekt, ne kód s větvením",
    icon: "▤",
    kind: "block",
    rules: {
      must: [
        "Fixture je hotový objekt nebo soubor s daty.",
        "Každý test si bere vlastní kopii.",
        "Jméno fixture říká, jaký stav popisuje.",
      ],
      mustNot: ["Žádné if uvnitř fixture.", "Žádný sdílený měnitelný stav mezi testy."],
    },
    decomposition: [
      { title: "Data", text: "Minimální stav, který test potřebuje." },
      { title: "Kopie", text: "Rozbalení do nového objektu na začátku testu." },
      { title: "Jméno", text: "Popisuje situaci, ne implementaci." },
    ],
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
    hint: "uv run pytest backend · npm test · npm run build a výstup v odpovědi",
    icon: "⌸",
    kind: "block",
    rules: {
      must: [
        "Před hlášením „hotovo“ běží všechny tři brány.",
        "Výstup bran je součástí odpovědi, ne tvrzení.",
        "Neúspěch brány znamená, že hotovo není.",
      ],
      mustNot: ["Žádné „mělo by to fungovat“ bez výstupu.", "Žádné vypnutí testu kvůli termínu."],
    },
    decomposition: [
      { title: "Backend", text: "uv run pytest backend." },
      { title: "Frontend", text: "npm test (vitest, bez DOM)." },
      { title: "Sestavení", text: "npm run build (tsc --noEmit + vite build)." },
    ],
    template: [
      "uv run pytest backend",
      "npm test",
      "npm run build",
    ].join("\n"),
  },
];
