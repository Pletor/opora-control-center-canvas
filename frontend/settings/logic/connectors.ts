/**
 * Katalog aplikací, které Opora napojuje.
 *
 * `planned` = napojení zatím není postavené. `live` = napojení existuje a jeho stav se čte ze
 * serveru, takže se v seznamu nikdy neukazuje jako pravda něco, co si jen pamatuje kód. Zapnutí
 * je nastavení celé aplikace, nikdy jednoho projektu (docs/pravidla-struktury.md, „Jedno rozhraní
 * pro všechny projekty“).
 */
export type ConnectorStatus = "planned" | "available" | "live";

export type Connector = {
  id: string;
  name: string;
  /** Co napojení přinese, jednou větou. */
  purpose: string;
  status: ConnectorStatus;
};

export const OPENVIKING_ID = "openviking";

export const CONNECTORS: Connector[] = [
  { id: "github", name: "GitHub", purpose: "Repozitáře projektu: připojení, spravovaná kopie mainu, větve.", status: "planned" },
  { id: "claude-code", name: "Claude Code", purpose: "Skills a commandy řízené z aplikace; agent pracující nad uzlem.", status: "planned" },
  { id: "mcp", name: "MCP server", purpose: "Rozhraní pro agenty nad API: strom, uzel, převzetí úkolu, výsledek.", status: "planned" },
  { id: "graphify", name: "Graphify", purpose: "Mapa znalostí projektu z kódu a dokumentů.", status: "planned" },
  { id: "archify", name: "Archify", purpose: "Architektonická mapa projektu jako explorovatelné HTML.", status: "planned" },
  {
    id: OPENVIKING_ID,
    name: "OpenViking – paměť rolí",
    purpose: "Paměť agenta podle role: co se kompetence naučila napříč projekty i u jedné karty.",
    status: "live",
  },
];

export const CONNECTOR_STATUS_LABEL: Record<ConnectorStatus, string> = {
  planned: "Připravujeme",
  available: "K dispozici",
  live: "Podle serveru",
};

/** Odpověď `GET /api/memory/status`; `status` je `disabled`, `unavailable`, `needs_provisioning`
 * (+ `missingRoles`) nebo `configured`. */
export type MemoryStatusResponse = { status: string; reason?: string; url?: string; missingRoles?: unknown };

/** Co se u živého napojení ukáže: štítek, jeho barva, jedna věta a poloha přepínače. */
export type LiveConnector = {
  label: string;
  tone: "planned" | "available" | "error" | "needs_provisioning";
  /** Věta ze serveru (důvod nebo adresa); nikdy se nenahrazuje vlastním výkladem. */
  detail: string;
  /** Poloha přepínače aplikace; `false`, dokud se stav nepřečte. */
  enabled: boolean;
  /** Co udělá tlačítko. */
  action: string;
  /** Hodnota, kterou tlačítko pošle do `POST /api/memory/settings`. */
  next: boolean;
  /** Dokud se stav nepřečetl, nemá se čím přepínat. */
  busy: boolean;
  /** Role bez klíče u OpenVikingu; prázdné mimo stav `needs_provisioning`. */
  missingRoles: string[];
};

const withUrl = (reason: string, url?: string): string =>
  url ? (reason ? `${reason} (${url})` : url) : reason;

/** Role bez klíče z `/status`; cizí tvar se čte jako „žádné role“, ne jako chyba. */
const missingRoleIds = (status: MemoryStatusResponse): string[] =>
  Array.isArray(status.missingRoles)
    ? status.missingRoles.filter((entry): entry is string => typeof entry === "string" && entry.length > 0)
    : [];

/**
 * Stav napojení na OpenViking pro seznam konektorů. Nenačtený stav je `Zjišťuji…`, ne „vypnuto“ —
 * neznalost se nikdy nevydává za odpověď serveru.
 */
export function memoryConnector(status: MemoryStatusResponse | null): LiveConnector {
  if (!status) {
    return { label: "Zjišťuji…", tone: "planned", detail: "Stav se čte z GET /api/memory/status.", enabled: false, action: "Zapnout", next: true, busy: true, missingRoles: [] };
  }
  if (status.status === "configured") {
    return { label: "K dispozici", tone: "available", detail: withUrl(status.reason ?? "", status.url), enabled: true, action: "Vypnout", next: false, busy: false, missingRoles: [] };
  }
  if (status.status === "needs_provisioning") {
    return {
      label: "Vyžaduje založení rolí", tone: "needs_provisioning",
      detail: withUrl(status.reason ?? "Role zatím nemají klíče v OpenViking.", status.url),
      enabled: true, action: "Vypnout", next: false, busy: false, missingRoles: missingRoleIds(status),
    };
  }
  if (status.status === "unavailable") {
    return { label: "Nedostupné", tone: "error", detail: withUrl(status.reason ?? "OpenViking neodpověděl.", status.url), enabled: true, action: "Vypnout", next: false, busy: false, missingRoles: [] };
  }
  if (status.status === "disabled") {
    return { label: "Vypnuto", tone: "planned", detail: status.reason ?? "Paměť rolí je v nastavení aplikace vypnutá.", enabled: false, action: "Zapnout", next: true, busy: false, missingRoles: [] };
  }
  return { label: "Neznámý stav", tone: "error", detail: `Server vrátil stav ${status.status || "bez jména"}.`, enabled: false, action: "Zapnout", next: true, busy: true, missingRoles: [] };
}

/** Tělo přepnutí paměti rolí; server přijme právě jedno pole a nic navíc. */
export function memorySettingsPayload(enabled: boolean): { enabled: boolean } {
  return { enabled };
}

export type ProvisionRoleError = { role: string; reason: string };
/** Odpověď `POST /api/memory/provision`; klíče samotné v ní nikdy nejsou. */
export type ProvisionResult = {
  status: string;
  account?: string;
  provisioned?: string[];
  reused?: string[];
  errors?: ProvisionRoleError[];
};

/** Tělo rozdání klíčů rolím; server ho vyžaduje jako výslovné potvrzení člověka. */
export function provisionPayload(): { confirmed: true } {
  return { confirmed: true };
}

/** Věta pro člověka po kliknutí na „Založit klíče rolí“ v seznamu konektorů. */
export function provisionResultSummary(result: ProvisionResult | null): string {
  if (!result) return "";
  const provisioned = Array.isArray(result.provisioned) ? result.provisioned : [];
  const reused = Array.isArray(result.reused) ? result.reused : [];
  const errors = Array.isArray(result.errors) ? result.errors : [];
  const parts: string[] = [];
  if (provisioned.length) parts.push(`Založeno: ${provisioned.join(", ")}.`);
  if (reused.length) parts.push(`Beze změny: ${reused.join(", ")}.`);
  if (errors.length) parts.push(`Nepodařilo se: ${errors.map((entry) => `${entry.role} (${entry.reason})`).join(", ")}.`);
  return parts.length ? parts.join(" ") : "Rozdání klíčů rolím neudělalo žádnou změnu.";
}
