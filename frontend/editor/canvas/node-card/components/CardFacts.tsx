import type { Setting } from "@/shared/desktop-state/logic/types";

export function resolveFacts(refs: string[], settings: Setting[]) {
  return refs.map(id => ({ id, fact: settings.find(setting => setting.id === id) }));
}
export default function CardFacts({ facts }: { facts: ReturnType<typeof resolveFacts> }) {
  if (!facts.length) return null;
  return <details className="nodrag nopan" style={{ padding: "6px 12px" }}>
    <summary>🔗 Fakta projektu · {facts.length}{facts.some(item => !item.fact) ? " · ⚠ chybějící odkaz" : ""}</summary>
    <dl>{facts.map(({ id, fact }) => <div key={id}><dt>{fact?.key ?? `Chybějící fakt ${id}`}</dt><dd style={{ whiteSpace: "pre-wrap" }}>{fact?.value ?? "Fakt byl odstraněn. Opravte odkaz v detailu karty."}</dd></div>)}</dl>
  </details>;
}
