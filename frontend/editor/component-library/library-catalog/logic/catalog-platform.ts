// Kategorie Cloud a infrastruktura a Cache. Prostředí se liší konfigurací, ne kódem; cache má klíč
// z otisku vstupů a padá se změnou zdroje, ne s hodinami. Tvar prvku: library-catalog.ts.
import type { CatalogItem } from "./library-catalog";

export const cloudItems: CatalogItem[] = [
  {
    id: "cloud-env-split",
    category: "cloud",
    label: "Konfigurace na jednom místě",
    purpose: "Dev a prod se liší jen hodnotami konfigurace; port, cesty a adresy se čtou z jednoho místa.",
    relates: [
      "@sec-no-secrets",
      "Backend, dev server (vite proxy) i skripty berou port a datovou složku odtud.",
    ],
    done: [
      "V logice není větev podle prostředí ani adresa natvrdo.",
      "README vyjmenuje proměnné prostředí a jejich výchozí hodnoty.",
    ],
    invariants: [],
    template: [
      "# backend/app/config.py",
      "@dataclass(frozen=True)",
      "class Config:",
      "    host: str = os.environ.get(\"OPORA_HOST\", \"127.0.0.1\")",
      "    port: int = int(os.environ.get(\"OPORA_PORT\", \"8740\"))",
    ].join("\n"),
  },
  {
    id: "cloud-repeatable-build",
    category: "cloud",
    label: "Build a deploy jako opakovatelné kroky",
    purpose: "Sestavení a nasazení jsou příkazy v README, které jdou spustit znovu se stejným výsledkem.",
    relates: ["@test-done-gates", "@cloud-env-split"],
    done: [
      "Čistý checkout se sestaví jen podle README.",
      "Selhání kroku ukončí build s nenulovým kódem.",
    ],
    invariants: [{ kind: "must_not", text: "Nenasazuje se strom, který neprošel branami hotovo." }],
    steps: [
      { title: "Kontrola", text: "Brány hotovo před sestavením." },
      { title: "Sestavení", text: "Jeden příkaz, jeden výstupní adresář." },
      { title: "Nasazení", text: "Přenos výstupu a restart služby." },
    ],
  },
  {
    id: "cloud-structured-log",
    category: "cloud",
    label: "Strukturovaný log s kontextem",
    purpose: "Záznam logu nese projekt, pracovní prostor a operaci, aby šel filtrovat strojově.",
    relates: ["@be-czech-error", "@ms-distributed-tracing"],
    done: ["Každý záznam má pole project, workspace a název události."],
    invariants: [{ kind: "must_not", text: "Do logu nejde tajemství ani obsah uživatele." }],
    template: [
      "# backend/app/logging.py",
      "log.info(\"library.insert\", extra={",
      "    \"project\": project, \"workspace\": workspace, \"item\": item_id,",
      "})",
    ].join("\n"),
  },
];

export const cacheItems: CatalogItem[] = [
  {
    id: "cache-digest-key",
    category: "cache",
    label: "Klíč z otisku vstupů",
    purpose: "Klíč cache je otisk všech vstupů a verze algoritmu, takže změna zdroje dá nový klíč a starou hodnotu zneplatní.",
    relates: ["@cache-ttl-fallback", "@cache-never-list", "Mapy projektu (archify, graphify) se cachují podle otisku cest."],
    done: [
      "Změna kteréhokoli vstupu dá jiný klíč (test).",
      "Neplatný záznam se přepočítá, nevrátí.",
    ],
    invariants: [{ kind: "must_not", text: "Klíč nevzniká z času ani z náhody." }],
    template: [
      "# backend/project/maps/cache.py",
      "def digest(paths: list[str], version: str) -> str:",
      "    payload = json.dumps({\"paths\": sorted(paths), \"v\": version}, sort_keys=True)",
      "    return hashlib.sha256(payload.encode()).hexdigest()",
    ].join("\n"),
  },
  {
    id: "cache-ttl-fallback",
    category: "cache",
    label: "TTL jen jako pojistka",
    purpose: "Vypršení jen uklízí staré záznamy; správnost drží klíč z otisku vstupů.",
    relates: ["@cache-digest-key", "@cloud-env-split"],
    done: ["Doba TTL je v konfiguraci a README říká, proč právě tolik."],
    invariants: [],
    template: [
      "# backend/project/maps/cache.py",
      "MAP_TTL_SECONDS = int(os.environ.get(\"OPORA_MAP_TTL\", \"86400\"))",
    ].join("\n"),
  },
  {
    id: "cache-never-list",
    category: "cache",
    label: "Co se necachuje",
    purpose: "Cachuje se jen drahé a stabilní; seznam výjimek je v README modulu.",
    relates: ["@be-cas-revision", "@sec-no-secrets", "@cache-digest-key"],
    done: ["README modulu vyjmenuje, co se cachuje a co ne."],
    invariants: [
      { kind: "must_not", text: "Necachuje se záznam s revizí a CAS ani odpověď s tajemstvím nebo právy." },
    ],
    template: [
      "# backend/project/maps/README.md",
      "# Cachujeme: artefakty map (archify, graphify) podle digestu cest.",
      "# Necachujeme: desktop stav (má revizi a CAS), podklady pro agenta, cokoli s právy.",
    ].join("\n"),
  },
];
