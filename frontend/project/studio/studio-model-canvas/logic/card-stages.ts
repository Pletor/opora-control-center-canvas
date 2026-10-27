// Tři stupně vnitřního fungování karty MODELu (prototyp `component-visuals.mjs`, `teachingStages`): co komponenta
// přijímá, čím prochází a co vydává. Čistě datová tabulka, jeden typ na řádek; neznámý typ dostane obecné stupně.

const STAGES: Readonly<Record<string, readonly [string, string, string]>> = {
  "client": ["Záměr", "Souběh", "Odpověď"], "frontend-app": ["HTTP vstup", "Statické", "API router"], "cdn-edge-cache": ["Požadavek", "Cache hit", "Origin"],
  "api-gateway": ["HTTP vstup", "Admission", "Deadline"], "load-balancer": ["Požadavek", "Rozdělení", "Backendy"],
  "service": ["Příjem", "Thread pool", "Typed effects"], "sync-client": ["Události", "Offline buffer", "Flush"], "circuit-breaker": ["Closed", "Open", "Half-open"],
  "monitoring": ["Vzorky", "Ingest", "Health"], "coordination-service": ["Příkazy", "Kapacita", "Události"], "workflow-orchestrator": ["Dispatch", "Job", "Efekty"],
  "host-policy-gate": ["Host", "Admission", "HTTP"], "kubernetes-deployment": ["Využití", "Repliky", "Kapacita"], "pod": ["HTTP vstup", "Sloty", "Typed effects"],
  "isolated-compute-pool": ["Job vstup", "Izolované sloty", "Výstup"], "postgresql": ["SQL vstup", "Connection pool", "Výsledky"],
  "postgresql-read-replica": ["Replication", "Ingest", "Čtení"], "object-storage": ["Data", "Kapacita", "Event"], "redis": ["Cache command", "Hit / miss", "Výsledek"],
  "partitioned-data-store": ["Record", "Partitions", "CDC"], "search-ranking-index": ["Index ingest", "Query", "Výsledek"], "geo-index": ["Location", "Spatial query", "Telemetry"],
  "analytical-store": ["Data ingest", "Queries", "Results"], "queue": ["Event vstup", "Backlog", "Job dispatch"], "message-broker": ["Append", "Backlog", "Consumers"],
  "worker": ["Job vstup", "Worker slots", "Efekty"], "event-producer": ["Záměr", "Kapacita", "Emit"], "scheduled-job-cron": ["Časovač", "Dávka", "Emit"],
  "stream-processor": ["Příjem", "Okno", "Emit"], "realtime-gateway": ["Event", "Příjemci", "Fan-out"], "api-adapter": ["Decode", "Convert", "HTTP"],
  "external-provider": ["Request", "Provider", "Result"], "etl-job": ["SQL result", "Batch", "Event"],
};

export const cardStages = (type: string): readonly string[] => STAGES[type] ?? ["Příjem", "Zpracování", "Výstup"];
