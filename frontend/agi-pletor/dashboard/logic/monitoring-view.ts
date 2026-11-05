import { list, rec, str, unavailable } from "./view-common";

export type MonitoringView = { enabled: boolean; hosts: { host: string; state: string }[]; events: { ts: string; type: string; author: string; payload: string }[]; problem: string };

const clip = (text: string, max = 100) => (text.length > max ? text.slice(0, max - 1) + "…" : text);

/** Odpověď `GET /api/pletor/monitoring` → hosté a události plátna 4 (nejnovější nahoře) s krátkým payloadem a autorem, je-li v události. */
export function monitoringView(raw: unknown): MonitoringView {
  const root = rec(raw);
  const hosts = list(root.hosts).map((item) => ({ host: str(rec(item).host), state: str(rec(item).state) || "—" }));
  const events = list(root.events).map((item) => {
    const event = rec(item);
    const payload = rec(event.payload);
    const author = str(event.author) || str(event.actor) || str(payload.author) || str(payload.actor) || "—";
    return { ts: str(event.ts), type: str(event.type), author, payload: clip(typeof event.payload === "string" ? event.payload : JSON.stringify(event.payload ?? "")) };
  }).reverse();
  return { enabled: root.enabled === true, hosts, events, problem: [unavailable(root.hosts), unavailable(root.events)].filter(Boolean).join(" · ") };
}
