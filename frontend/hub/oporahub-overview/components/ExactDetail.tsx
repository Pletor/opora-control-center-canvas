import type { ReactNode } from "react";

/** A bounded-history fallback must never become another record's actionable detail. */
export default function ExactDetail({ requestedId, selectedId, busy, error, children }: {
  requestedId?: string; selectedId?: string; busy: boolean; error: string; children: ReactNode;
}) {
  if (!requestedId || requestedId === selectedId) return <>{children}</>;
  if (busy) return <p role="status">Načítám přesně vybraný záznam…</p>;
  return <div role="alert"><p>Vybraný záznam není dostupný v načteném výběru. Nebyl nahrazen jiným záznamem.</p>{error && <p>{error}</p>}</div>;
}
