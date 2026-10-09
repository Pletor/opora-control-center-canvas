// Výzkum a ověřování: vlevo karty výzkumů s kuličkou verdiktu (reálné · slepá ulička · nereálné · neověřeno),
// vpravo detail vybraného (ResearchDetail). Výběr drží tento dílek; zápisy dělá detail přes vaultOp.
import { useState } from "react";
import type { Feedback, VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { RESEARCH_STATUS, VERDICTS, researchItems } from "../logic/vault-window-model";
import type { VaultScope } from "../logic/vault-actions";
import ResearchDetail from "./ResearchDetail";

export function VerdictMark({ verdict }: { verdict: keyof typeof VERDICTS }) {
  const info = VERDICTS[verdict];
  return (
    <span className={"vault-verdict vault-verdict--" + info.tone}>
      <span className="vault-verdict__dot" aria-hidden="true" />{info.label}
    </span>
  );
}

export default function ResearchSection({ scope, roots, query, feedback, readOnly, initial }: {
  scope: VaultScope;
  roots: VaultNode[];
  query: string;
  feedback: Feedback[];
  readOnly: boolean;
  initial?: string | null;
}) {
  const items = researchItems(roots, query);
  const [picked, setPicked] = useState<string | null>(initial ?? null);
  const current = items.find((item) => item.node.id === picked) ?? items[0];
  if (!items.length) {
    return (
      <div className="vault-window__empty" data-testid="vault-research-empty">
        <p><strong>{query ? "Hledání nenašlo žádný výzkum." : "Zatím žádný výzkum."}</strong></p>
        <p>Výzkum ověřuje, jestli je část zadání reálná, slepá ulička, nebo nereálná, a sbírá důkazy s odkazy.
          Zadáš ho v sekci Zadání u kapitoly („Zadat výzkum“); agent dostane balíček s cílem, textem a tvou zpětnou vazbou.</p>
      </div>
    );
  }
  return (
    <div className="vault-split" data-testid="vault-research">
      <div className="vault-stack">
        {items.map((item) => {
          const research = item.node.research;
          const count = feedback.filter((entry) => entry.fragmentId === item.node.id).length;
          return (
            <button key={item.node.id} type="button" className="vault-research-card" aria-pressed={item.node.id === current?.node.id}
              onClick={() => setPicked(item.node.id)}>
              <span className="vault-research-card__top">
                <VerdictMark verdict={research?.verdict ?? "unverified"} />
                <span className="vault-research-card__where">{item.parent?.title ?? ""}</span>
              </span>
              <span className="vault-research-card__question">{research?.question || item.node.title}</span>
              <span className="vault-research-card__meta">
                {research ? `${research.evidence} ${research.evidence === 1 ? "důkaz" : research.evidence >= 2 && research.evidence <= 4 ? "důkazy" : "důkazů"} · kolo ${research.round} · ${RESEARCH_STATUS[research.status]}` : "bez výsledku"}
                {count ? ` · zpětná vazba ${count}` : ""}
              </span>
            </button>
          );
        })}
      </div>
      {current && <ResearchDetail key={current.node.id} scope={scope} item={current} readOnly={readOnly} />}
    </div>
  );
}
