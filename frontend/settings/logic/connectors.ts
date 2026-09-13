/** Katalog aplikací, které Opora napojuje. Stav "planned" = napojení zatím není postavené. */
export type ConnectorStatus = "planned" | "available";

export type Connector = {
  id: string;
  name: string;
  /** Co napojení přinese, jednou větou. */
  purpose: string;
  status: ConnectorStatus;
};

export const CONNECTORS: Connector[] = [
  { id: "github", name: "GitHub", purpose: "Repozitáře projektu: připojení, spravovaná kopie mainu, větve.", status: "planned" },
  { id: "claude-code", name: "Claude Code", purpose: "Hooky, skills a commandy řízené z aplikace; agent pracující nad uzlem.", status: "planned" },
  { id: "mcp", name: "MCP server", purpose: "Rozhraní pro agenty nad API: strom, uzel, převzetí úkolu, výsledek.", status: "planned" },
  { id: "hermes", name: "Hermes", purpose: "Živé session agentů navázané na uzel v Live Run.", status: "planned" },
  { id: "graphify", name: "Graphify", purpose: "Mapa znalostí projektu z kódu a dokumentů.", status: "planned" },
  { id: "archify", name: "Archify", purpose: "Architektonická mapa projektu jako explorovatelné HTML.", status: "planned" },
];

export const CONNECTOR_STATUS_LABEL: Record<ConnectorStatus, string> = {
  planned: "Připravujeme",
  available: "K dispozici",
};
