// Prvky, které dávají smysl jen některým projektům: kategorie Multitenance a prvky pro mikroslužby,
// modulární monolit a serverless. Každý nese `fits` (docs/suplik-a-profil.md). Architektonická
// pravidla z bývalé kategorie Pravidla Agentů tu žijí jako invarianty prvku, ke kterému patří
// (docs/menu-a-katalog.md §B3). Tvar prvku: library-catalog.ts.
import type { CatalogItem } from "./library-catalog";

export const tenancyItems: CatalogItem[] = [
  {
    id: "tenant-request-context",
    category: "tenancy",
    fits: { tenancy: ["multi"] },
    label: "Kontext tenanta v požadavku",
    purpose: "Middleware určí tenanta z přihlášení jednou na vstupu a dál ho předává modulům parametrem.",
    relates: ["@tenant-data-isolation", "@sec-server-validation", "Identita přichází z relace nebo tokenu, ne z těla požadavku."],
    done: [
      "Požadavek bez rozpoznaného tenanta skončí chybou dřív, než sáhne na data (test).",
      "Tenant poslaný klientem v těle požadavku se ignoruje (test).",
    ],
    invariants: [
      { kind: "must_not", text: "Tenant se nikdy nebere z těla požadavku od klienta, jen z přihlášení." },
      { kind: "must_not", text: "Když tenanta nejde určit, nepoužije se žádný výchozí." },
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
    fits: { tenancy: ["multi"] },
    label: "Izolace dat podle tenanta",
    purpose: "Data zákazníka nesou tenant_id (nebo leží ve schématu či databázi tenanta) a podmínku na tenanta přidává repozitář.",
    relates: ["@tenant-request-context", "@db-table-owner", "@test-fixture-data"],
    done: [
      "Test se dvěma tenanty ověří, že tenant A nevidí data tenanta B.",
      "Unikátní indexy zahrnují tenanta.",
    ],
    invariants: [
      { kind: "must", text: "Každý dotaz na data zákazníka filtruje podle tenanta z kontextu požadavku." },
    ],
    steps: [
      { title: "Model izolace", text: "Sloupec tenant_id, schéma na tenanta, nebo databáze na tenanta." },
      { title: "Repozitář", text: "Podmínku na tenanta přidá na jednom místě (nebo row-level security)." },
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
    fits: { tenancy: ["multi"] },
    label: "Konfigurace a limity tenanta",
    purpose: "Tarif, kvóty a zapnuté funkce tenanta jsou data s výchozími hodnotami a limit se ověřuje na jednom místě.",
    relates: ["@tenant-request-context", "@be-czech-error"],
    done: [
      "Překročení limitu vrátí českou chybu, který limit a proč.",
      "Změna nastavení jednoho tenanta neovlivní ostatní (test).",
    ],
    invariants: [{ kind: "must_not", text: "V logice není větev podle konkrétního tenanta ani limit natvrdo." }],
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
    purpose: "Modul vystavuje veřejné funkce na jednom místě; vnitřek a tabulky modulu jsou jeho soukromé.",
    relates: ["@db-table-owner", "@be-environment-router", "Závislosti mezi moduly jdou jedním směrem a popisuje je README."],
    done: [
      "Ostatní moduly importují jen z veřejného API modulu (test nebo lint).",
      "Ke každé tabulce je jasný vlastnický modul.",
    ],
    invariants: [
      { kind: "must_not", text: "Modul neimportuje z vnitřku cizího modulu." },
      { kind: "must_not", text: "Modul nečte ani nepíše tabulky cizího modulu; cizí data bere přes jeho veřejné API." },
    ],
    fits: { architecture: ["modular"] },
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
    purpose: "Služby si posílají verzované události přes frontu nebo téma brokeru, ne přímým voláním.",
    relates: ["@ms-service-database", "@ms-distributed-tracing", "@sls-managed-queue"],
    done: [
      "Stejná zpráva doručená dvakrát nic nezmění (test idempotence).",
      "Opakovaně selhaná zpráva skončí ve frontě nedoručených.",
    ],
    invariants: [{ kind: "must_not", text: "Příjemce nespoléhá na pořadí doručení, které broker nezaručuje." }],
    fits: { architecture: ["microservices"] },
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
    purpose: "Každá služba vlastní svou databázi nebo schéma; ostatní služby jdou přes její API nebo události.",
    relates: ["@ms-message-broker", "@db-reversible-migration", "Migrace služby se nasazují spolu se službou."],
    done: ["Konfigurace služby obsahuje jen její vlastní databázi."],
    invariants: [
      { kind: "must_not", text: "Služba se nepřipojuje k databázi jiné služby a nesdílí s ní tabulku." },
    ],
    fits: { architecture: ["microservices"] },
    template: [
      "# services/orders/config.py",
      "DATABASE_URL = os.environ[\"ORDERS_DATABASE_URL\"]  # jen služba orders",
    ].join("\n"),
  },
  {
    id: "ms-api-gateway",
    category: "cloud",
    label: "API gateway",
    purpose: "Jediný vstup zvenku: směruje na služby a jednotně ověřuje identitu a limity požadavků.",
    relates: ["@ms-distributed-tracing", "@sec-server-validation", "Směrovací pravidla jsou v konfiguraci pod verzí."],
    done: ["Klient zná jen adresu gateway a žádná služba není vystavená mimo ni."],
    invariants: [{ kind: "must_not", text: "Gateway nenese doménovou logiku." }],
    fits: { architecture: ["microservices"] },
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
    purpose: "Jedno trace id vznikne na vstupu a projde všemi službami, událostmi a logy.",
    relates: ["@cloud-structured-log", "@ms-api-gateway", "@ms-message-broker"],
    done: ["Z logů jde podle trace id složit celou cestu požadavku."],
    invariants: [{ kind: "must_not", text: "Uprostřed řetězce nevzniká nové trace id, když už jedno přišlo." }],
    fits: { architecture: ["microservices"] },
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
    purpose: "Krátká bezstavová funkce zpracuje jednu událost; stav žije ve spravované službě.",
    relates: ["@sls-managed-queue", "@sec-no-secrets", "@fe-pure-model"],
    done: [
      "Logika je čistá funkce testovatelná bez platformy.",
      "Opakované doručení téže události nic nerozbije.",
    ],
    invariants: [
      { kind: "must_not", text: "Funkce si nedrží stav v paměti ani na disku mezi voláními." },
    ],
    fits: { architecture: ["serverless"] },
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
    purpose: "Práce, která nemusí hned, jde do fronty platformy a odebírá ji funkce.",
    relates: ["@sls-function", "@ms-message-broker"],
    done: ["Zpráva po vyčerpání pokusů skončí ve frontě nedoručených."],
    invariants: [{ kind: "must_not", text: "Zpracování nespoléhá na to, že zpráva přijde právě jednou." }],
    fits: { architecture: ["serverless"] },
    template: [
      "# functions/send_email/handler.py",
      "def handler(event, context):",
      "    for record in event[\"Records\"]:",
      "        send_once(record[\"messageId\"], parse(record[\"body\"]))",
    ].join("\n"),
  },
];
