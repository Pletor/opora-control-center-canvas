// Prvky, které dávají smysl jen některým projektům: kategorie Multitenance a prvky pro mikroslužby,
// modulární monolit a serverless. Každý nese `fits` (docs/suplik-a-profil.md), takže projekt jiného
// profilu ho najde jen pod „Mimo profil“ nebo hledáním. Tvar je stejný jako u sousedů: pravidla,
// rozpad a krátká kostra kódu v konvencích tohoto repozitáře.
import type { CatalogItem } from "./library-catalog";

export const tenancyItems: CatalogItem[] = [
  {
    id: "tenant-request-context",
    category: "tenancy",
    label: "Kontext tenanta v požadavku",
    hint: "Middleware určí tenanta dřív, než požadavek sáhne na data",
    icon: "◎",
    kind: "card",
    fits: { tenancy: ["multi"] },
    rules: {
      must: [
        "Tenant se určí jednou na vstupu požadavku (doména, token, hlavička) a dál se předává.",
        "Požadavek bez rozpoznaného tenanta skončí chybou dřív, než se dotkne dat.",
        "Tenant z přihlášení má přednost před tím, co pošle klient v těle požadavku.",
      ],
      mustNot: ["Žádné čtení tenanta z globální proměnné sdílené mezi požadavky.", "Žádný výchozí tenant, když se určit nedá."],
    },
    decomposition: [
      { title: "Middleware", text: "Přečte identitu a určí tenanta." },
      { title: "Kontext", text: "Tenant putuje s požadavkem do modulu jako parametr." },
      { title: "Test", text: "Požadavek bez tenanta a s cizím tenantem končí chybou." },
    ],
    template: [
      "# backend/app/tenant_context.py",
      "def tenant_of(request) -> str:",
      "    tenant = request.state.identity.tenant_id",
      "    if not tenant:",
      "        raise PermissionError(\"Požadavek nepatří žádnému tenantovi.\")",
      "    return tenant",
    ].join("\n"),
  },
  {
    id: "tenant-data-isolation",
    category: "tenancy",
    label: "Izolace dat podle tenanta",
    hint: "Řádek nese tenant_id, nebo má tenant vlastní schéma či databázi",
    icon: "▦",
    kind: "card",
    fits: { tenancy: ["multi"] },
    rules: {
      must: [
        "Každá tabulka s daty zákazníka má tenant_id, nebo leží ve schématu či databázi tenanta.",
        "Každý dotaz filtruje podle tenanta na jednom místě (repozitář, row-level security).",
        "Test ověří, že tenant A nevidí data tenanta B.",
      ],
      mustNot: ["Žádný dotaz bez podmínky na tenanta.", "Žádný unikátní index, který tenanta vynechá."],
    },
    decomposition: [
      { title: "Model izolace", text: "Sloupec tenant_id, schéma na tenanta, nebo databáze na tenanta." },
      { title: "Přístup k datům", text: "Repozitář přidá podmínku na tenanta sám." },
      { title: "Test úniku", text: "Dva tenanti, stejná data, žádný průnik." },
    ],
    template: [
      "# database/repositories/orders.py",
      "def list_orders(db, tenant_id: str) -> list[dict]:",
      "    return db.execute(",
      "        \"SELECT * FROM orders WHERE tenant_id=? ORDER BY created_at\", (tenant_id,)",
      "    ).fetchall()",
    ].join("\n"),
  },
  {
    id: "tenant-config-limits",
    category: "tenancy",
    label: "Konfigurace a limity tenanta",
    hint: "Tarif, kvóty a zapnuté funkce se čtou z nastavení tenanta, ne z kódu",
    icon: "⚙",
    kind: "card",
    fits: { tenancy: ["multi"] },
    rules: {
      must: [
        "Nastavení tenanta (tarif, kvóty, zapnuté funkce) je v datech a má výchozí hodnoty.",
        "Překročení limitu vrací srozumitelnou chybu, ne tiché oříznutí.",
        "Změna nastavení tenanta neovlivní ostatní tenanty.",
      ],
      mustNot: ["Žádné if tenant == \"…\" v logice.", "Žádný limit natvrdo v kódu."],
    },
    decomposition: [
      { title: "Nastavení", text: "Tabulka nastavení tenanta s výchozími hodnotami." },
      { title: "Kontrola", text: "Jedno místo, které limit ověří před akcí." },
      { title: "Hláška", text: "Česká chyba, který limit a proč." },
    ],
    template: [
      "# backend/<modul>/tenant_limits.py",
      "def ensure_quota(settings: dict, used: int) -> None:",
      "    if used >= settings.get(\"max_projects\", 3):",
      "        raise ValueError(\"Tarif nedovoluje další projekt.\")",
    ].join("\n"),
  },
];

export const architectureItems: CatalogItem[] = [
  {
    id: "be-module-boundary",
    category: "backend",
    label: "Hranice modulu",
    hint: "Veřejné API modulu je jeden vstup, vnitřek modulu je soukromý",
    icon: "▣",
    kind: "card",
    fits: { architecture: ["modular"] },
    rules: {
      must: [
        "Modul vystavuje veřejné funkce na jednom místě; ostatní moduly volají jen je.",
        "Tabulky modulu čte a píše jen modul sám.",
        "Závislosti mezi moduly jdou jedním směrem a jsou popsané v README.",
      ],
      mustNot: ["Žádný import z vnitřku cizího modulu.", "Žádný dotaz do tabulek cizího modulu."],
    },
    decomposition: [
      { title: "Veřejné API", text: "Soubor modulu s funkcemi, které smí volat ostatní." },
      { title: "Vnitřek", text: "Logika a přístup k datům modulu." },
      { title: "Kontrola", text: "Test nebo lint hlídá, že nikdo nesahá do vnitřku." },
    ],
    template: [
      "# backend/billing/__init__.py",
      "from .invoices import create_invoice, invoice_status",
      "",
      "__all__ = [\"create_invoice\", \"invoice_status\"]",
    ].join("\n"),
  },
  {
    id: "ms-message-broker",
    category: "backend",
    label: "Broker zpráv mezi službami",
    hint: "Služby si posílají události přes frontu, ne přímým voláním",
    icon: "⇶",
    kind: "card",
    fits: { architecture: ["microservices"] },
    rules: {
      must: [
        "Událost má verzovaný tvar a jméno v minulém čase (objednavka_vytvorena).",
        "Příjemce je idempotentní: stejná zpráva doručená dvakrát nic nerozbije.",
        "Zpráva, která opakovaně selže, skončí ve frontě nedoručených, ne v nekonečné smyčce.",
      ],
      mustNot: ["Žádné spoléhání na pořadí doručení, pokud ho broker nezaručuje.", "Žádná data jiné služby v těle zprávy navíc."],
    },
    decomposition: [
      { title: "Odesílatel", text: "Zapíše změnu a zveřejní událost." },
      { title: "Broker", text: "Fronta nebo téma s potvrzením doručení." },
      { title: "Příjemce", text: "Zpracuje událost idempotentně podle jejího id." },
    ],
    template: [
      "# services/orders/events.py",
      "def publish_order_created(broker, order: dict) -> None:",
      "    broker.publish(\"orders.order_created.v1\", {",
      "        \"event_id\": order[\"event_id\"], \"order_id\": order[\"id\"],",
      "    })",
    ].join("\n"),
  },
  {
    id: "ms-service-database",
    category: "database",
    label: "Vlastní databáze služby",
    hint: "Každá služba vlastní svá data; ostatní se ptají přes její API",
    icon: "⛁",
    kind: "card",
    fits: { architecture: ["microservices"] },
    rules: {
      must: [
        "Služba má vlastní databázi nebo schéma a jen ona do něj píše.",
        "Data jiné služby se čtou přes její API nebo z událostí, ne dotazem do cizí databáze.",
        "Migrace služby se nasazují spolu se službou.",
      ],
      mustNot: ["Žádná sdílená tabulka mezi službami.", "Žádný JOIN přes databáze dvou služeb."],
    },
    decomposition: [
      { title: "Úložiště", text: "Databáze nebo schéma patří jedné službě." },
      { title: "Přístup", text: "Ostatní služby jen přes API nebo události." },
      { title: "Kopie dat", text: "Potřebná cizí data si služba drží jako vlastní projekci z událostí." },
    ],
    template: [
      "# services/orders/config.py",
      "DATABASE_URL = os.environ[\"ORDERS_DATABASE_URL\"]  # jen služba orders",
    ].join("\n"),
  },
  {
    id: "ms-api-gateway",
    category: "cloud",
    label: "API gateway",
    hint: "Jeden vstup zvenku: směrování na služby, ověření a limity na jednom místě",
    icon: "⇄",
    kind: "card",
    fits: { architecture: ["microservices"] },
    rules: {
      must: [
        "Klient zná jen adresu gateway, ne adresy jednotlivých služeb.",
        "Ověření identity a limity požadavků řeší gateway jednotně.",
        "Směrovací pravidla jsou v konfiguraci pod verzí.",
      ],
      mustNot: ["Žádná doménová logika v gateway.", "Žádná služba vystavená ven mimo gateway."],
    },
    decomposition: [
      { title: "Směrování", text: "Cesta → služba podle konfigurace." },
      { title: "Ověření", text: "Token se ověří jednou a identita jde dál v hlavičce." },
      { title: "Limity", text: "Omezení počtu požadavků na klienta." },
    ],
    template: [
      "# gateway/routes.yaml",
      "routes:",
      "  - path: /api/orders",
      "    service: orders",
      "  - path: /api/billing",
      "    service: billing",
    ].join("\n"),
  },
  {
    id: "ms-distributed-tracing",
    category: "cloud",
    label: "Distribuované trasování",
    hint: "Jedno id požadavku prochází všemi službami a logy",
    icon: "⋯",
    kind: "block",
    fits: { architecture: ["microservices"] },
    rules: {
      must: [
        "Každý požadavek dostane trace id na vstupu a každá služba ho předá dál.",
        "Logy a události nesou trace id, aby šlo složit celou cestu požadavku.",
      ],
      mustNot: ["Žádné nové trace id uprostřed řetězce, pokud už jedno přišlo."],
    },
    decomposition: [
      { title: "Vstup", text: "Gateway nebo první služba id vytvoří." },
      { title: "Předání", text: "HTTP hlavička nebo pole zprávy nese id dál." },
      { title: "Log", text: "Strukturovaný log zapisuje id ke každému řádku." },
    ],
    template: [
      "# services/shared/tracing.py",
      "def outgoing_headers(request) -> dict:",
      "    return {\"traceparent\": request.headers.get(\"traceparent\") or new_traceparent()}",
    ].join("\n"),
  },
  {
    id: "sls-function",
    category: "backend",
    label: "Funkce (serverless)",
    hint: "Krátká bezstavová funkce na jednu událost; stav žije ve spravované službě",
    icon: "ƒ",
    kind: "card",
    fits: { architecture: ["serverless"] },
    rules: {
      must: [
        "Funkce zpracuje jednu událost a skončí; nic si nepamatuje mezi voláními.",
        "Konfigurace přichází z proměnných prostředí, tajemství ze správce tajemství.",
        "Opakované doručení téže události nic nerozbije.",
      ],
      mustNot: ["Žádný stav v paměti nebo na disku funkce mezi voláními.", "Žádná dlouhá práce, která se nevejde do časového limitu platformy."],
    },
    decomposition: [
      { title: "Handler", text: "Přijme událost, ověří tvar, zavolá logiku." },
      { title: "Logika", text: "Čistá funkce testovatelná bez platformy." },
      { title: "Výstup", text: "Zápis do spravované služby nebo další událost." },
    ],
    template: [
      "# functions/resize_image/handler.py",
      "def handler(event, context):",
      "    image = parse_upload(event)",
      "    return store_thumbnail(resize(image))",
    ].join("\n"),
  },
  {
    id: "sls-managed-queue",
    category: "cloud",
    label: "Spravovaná fronta",
    hint: "Práce, která nemusí hned, jde do fronty platformy a funkce ji odebírá",
    icon: "≡",
    kind: "block",
    fits: { architecture: ["serverless"] },
    rules: {
      must: [
        "Zpráva nese všechno, co funkce potřebuje, nebo odkaz na to.",
        "Selhaná zpráva se po několika pokusech přesune do fronty nedoručených.",
      ],
      mustNot: ["Žádné spoléhání na to, že zpráva přijde právě jednou."],
    },
    decomposition: [
      { title: "Fronta", text: "Spravovaná služba platformy s nastavenými pokusy." },
      { title: "Odběratel", text: "Funkce zpracuje dávku zpráv." },
      { title: "Nedoručené", text: "Vlastní fronta pro zprávy, které opakovaně selhaly." },
    ],
    template: [
      "# functions/send_email/handler.py",
      "def handler(event, context):",
      "    for record in event[\"Records\"]:",
      "        send_once(record[\"messageId\"], parse(record[\"body\"]))",
    ].join("\n"),
  },
];
