// Kategorie Cloud a infrastruktura (blok 7) a Cache (blok 8) sektoru. Prostředí se liší konfigurací,
// ne kódem; cache má klíč z digestu vstupů a umírá se změnou zdroje, ne s hodinami.
import type { CatalogItem } from "./library-catalog";

export const cloudItems: CatalogItem[] = [
  {
    id: "cloud-env-split",
    category: "cloud",
    label: "Dev a prod jen konfigurací",
    hint: "Stejný kód, jiné hodnoty; větev podle prostředí nikde v kódu",
    icon: "◫",
    kind: "card",
    rules: {
      must: [
        "Rozdíl mezi prostředími je hodnota v konfiguraci.",
        "Konfigurace se čte na jednom místě a předává dál.",
        "Výchozí hodnoty jsou bezpečné pro vývoj.",
      ],
      mustNot: ["Žádné if prostředí == \"prod\" v logice.", "Žádná produkční adresa natvrdo v kódu."],
    },
    decomposition: [
      { title: "Načtení", text: "Jedno místo, kde se konfigurace čte a ověřuje." },
      { title: "Předání", text: "Hodnoty jdou do modulů parametrem." },
      { title: "Doklad", text: "README říká, které proměnné prostředí existují." },
    ],
    template: [
      "# backend/app/config.py",
      "@dataclass(frozen=True)",
      "class Config:",
      "    host: str = os.environ.get(\"OPORA_HOST\", \"127.0.0.1\")",
      "    port: int = int(os.environ.get(\"OPORA_PORT\", \"8740\"))",
    ].join("\n"),
  },
  {
    id: "cloud-env-vars",
    category: "cloud",
    label: "Env proměnné bez tajemství v repozitáři",
    hint: "V gitu je jen vzor .env.example, hodnoty zůstávají venku",
    icon: "⚙",
    kind: "block",
    rules: {
      must: [
        "V repozitáři je jen vzor s prázdnými hodnotami.",
        "Chybějící povinná proměnná zastaví start s jasnou hláškou.",
        "Jméno proměnné má předponu aplikace.",
      ],
      mustNot: ["Žádný soubor .env v gitu.", "Žádné tajemství v logu ani v hlášce chyby."],
    },
    decomposition: [
      { title: "Vzor", text: ".env.example se seznamem jmen." },
      { title: "Kontrola", text: "Start ověří, že povinné proměnné existují." },
      { title: "Ignorace", text: ".gitignore drží skutečné hodnoty venku." },
    ],
    template: [
      "# .env.example",
      "OPORA_HOST=127.0.0.1",
      "OPORA_PORT=8740",
      "OPORA_DATA_DIR=",
    ].join("\n"),
  },
  {
    id: "cloud-repeatable-build",
    category: "cloud",
    label: "Build a deploy jako opakovatelné kroky",
    hint: "Příkazy v README; co nejde zopakovat, není postup",
    icon: "⟳",
    kind: "card",
    rules: {
      must: [
        "Každý krok je příkaz, který jde spustit znovu se stejným výsledkem.",
        "Kroky jsou v README projektu, ne v hlavě.",
        "Build selže hlasitě, ne tiše s polovičním výsledkem.",
      ],
      mustNot: ["Žádný ruční krok bez záznamu.", "Žádný deploy z neověřeného stromu."],
    },
    decomposition: [
      { title: "Kontrola", text: "Testy a typy před sestavením." },
      { title: "Sestavení", text: "Jeden příkaz, jeden výstupní adresář." },
      { title: "Nasazení", text: "Přenos výstupu a restart služby." },
    ],
    template: [
      "# README.md – Build",
      "uv run pytest backend",
      "npm test",
      "npm run build",
    ].join("\n"),
  },
  {
    id: "cloud-structured-log",
    category: "cloud",
    label: "Strukturovaný log s kontextem",
    hint: "Řádek logu nese projekt a pracovní prostor, ne jen větu",
    icon: "≣",
    kind: "block",
    rules: {
      must: [
        "Každý záznam nese projekt, pracovní prostor a operaci.",
        "Úroveň odpovídá dopadu (info / warning / error).",
        "Log se dá filtrovat strojově.",
      ],
      mustNot: ["Žádné tajemství ani obsah uživatele v logu.", "Žádný print místo logu."],
    },
    decomposition: [
      { title: "Kontext", text: "Projekt, prostor, uzel — vždy stejná jména polí." },
      { title: "Událost", text: "Co se stalo, jedním slovem." },
      { title: "Míra", text: "Trvání nebo počet, aby šlo měřit." },
    ],
    template: [
      "# backend/app/logging.py",
      "log.info(\"library.insert\", extra={",
      "    \"project\": project, \"workspace\": workspace, \"item\": item_id,",
      "})",
    ].join("\n"),
  },
  {
    id: "cloud-single-source-ports",
    category: "cloud",
    label: "Jeden zdroj pravdy pro porty a cesty",
    hint: "Port a datová složka se definují jednou a všichni je čtou odtud",
    icon: "⌂",
    kind: "block",
    rules: {
      must: [
        "Port a cesty jsou v konfiguraci na jednom místě.",
        "Frontend i skripty berou hodnotu odtud, ne z paměti.",
        "Změna hodnoty se projeví bez hledání v kódu.",
      ],
      mustNot: ["Žádný port opsaný na třech místech.", "Žádná absolutní cesta uživatele v repozitáři."],
    },
    decomposition: [
      { title: "Definice", text: "Jedno místo s portem a datovým adresářem." },
      { title: "Odběratelé", text: "Backend, dev server a nástroje čtou totéž." },
      { title: "Doklad", text: "README ukazuje, kde hodnota bydlí." },
    ],
    template: [
      "// vite.config.ts",
      "server: { proxy: { \"/api\": \"http://127.0.0.1:8740\" } },",
    ].join("\n"),
  },
];

export const cacheItems: CatalogItem[] = [
  {
    id: "cache-digest-key",
    category: "cache",
    label: "Klíč z digestu vstupů",
    hint: "Klíč je otisk toho, z čeho hodnota vznikla",
    icon: "#",
    kind: "card",
    rules: {
      must: [
        "Klíč obsahuje všechny vstupy, ze kterých hodnota vznikla.",
        "Změna kteréhokoli vstupu dá jiný klíč.",
        "Verze algoritmu je součástí klíče.",
      ],
      mustNot: ["Žádný klíč z času nebo náhody.", "Žádný klíč, který nejde odvodit znovu."],
    },
    decomposition: [
      { title: "Vstupy", text: "Seznam toho, na čem hodnota závisí." },
      { title: "Otisk", text: "Stabilní hash ze setříděných vstupů." },
      { title: "Uložení", text: "Hodnota pod klíčem, vedle ní vstupy pro kontrolu." },
    ],
    template: [
      "# backend/project/maps/cache.py",
      "def digest(paths: list[str], version: str) -> str:",
      "    payload = json.dumps({\"paths\": sorted(paths), \"v\": version}, sort_keys=True)",
      "    return hashlib.sha256(payload.encode()).hexdigest()",
    ].join("\n"),
  },
  {
    id: "cache-invalidate-on-source",
    category: "cache",
    label: "Invalidace při změně zdroje",
    hint: "Hodnota padá se změnou vstupu, ne s hodinami",
    icon: "⌁",
    kind: "block",
    rules: {
      must: [
        "Změna zdroje zneplatní záznam okamžitě.",
        "Zneplatnění je bod v kódu, ne úklid na pozadí.",
        "Neplatný záznam se přepočítá, ne vrátí.",
      ],
      mustNot: ["Žádné čekání na vypršení TTL u změněného zdroje.", "Žádné mazání celé cache kvůli jednomu vstupu."],
    },
    decomposition: [
      { title: "Zdroj", text: "Co hodnotu určuje (soubor, revize, seznam cest)." },
      { title: "Hlídka", text: "Porovnání otisku při čtení." },
      { title: "Přepočet", text: "Nová hodnota pod novým klíčem." },
    ],
    template: [
      "# backend/project/maps/cache.py",
      "def get_or_build(key: str, build):",
      "    hit = store.get(key)",
      "    return hit if hit is not None else store.put(key, build())",
    ].join("\n"),
  },
  {
    id: "cache-ttl-fallback",
    category: "cache",
    label: "TTL jen jako pojistka",
    hint: "Čas je záchranná brzda, ne hlavní pravidlo",
    icon: "⏱",
    kind: "block",
    rules: {
      must: [
        "TTL je delší než obvyklá doba mezi změnami zdroje.",
        "Vypršení jen uklízí, nenahrazuje invalidaci.",
        "Doba je v konfiguraci, ne v kódu.",
      ],
      mustNot: ["Žádná správnost postavená na krátkém TTL.", "Žádné TTL u dat s revizí."],
    },
    decomposition: [
      { title: "Hodnota", text: "Kolik času je únosné." },
      { title: "Úklid", text: "Vypršené záznamy se zahodí." },
      { title: "Doklad", text: "README říká, proč právě tolik." },
    ],
    template: [
      "# backend/project/maps/cache.py",
      "MAP_TTL_SECONDS = int(os.environ.get(\"OPORA_MAP_TTL\", \"86400\"))",
    ].join("\n"),
  },
  {
    id: "cache-never-list",
    category: "cache",
    label: "Co se necachuje",
    hint: "Revizovaná data, stav s CAS a cokoli s tajemstvím",
    icon: "⊘",
    kind: "block",
    rules: {
      must: [
        "Cachuje se jen drahé a stabilní (mapy, balíčky, náhledy).",
        "Seznam výjimek je napsaný v README modulu.",
        "Každý cachovaný druh má vlastníka.",
      ],
      mustNot: [
        "Žádná cache nad záznamem s revizí a CAS.",
        "Žádná cache nad odpovědí, která nese tajemství nebo práva.",
      ],
    },
    decomposition: [
      { title: "Ano", text: "Drahé odvozeniny s jasnými vstupy." },
      { title: "Ne", text: "Stav, práva, tajemství, cokoli s revizí." },
      { title: "Hranice", text: "Kde se rozhoduje, aby to nebylo na dvou místech." },
    ],
    template: [
      "# backend/project/maps/README.md",
      "# Cachujeme: artefakty map (archify, graphify) podle digestu cest.",
      "# Necachujeme: desktop stav (má revizi a CAS), podklady pro agenta, cokoli s právy.",
    ].join("\n"),
  },
];
