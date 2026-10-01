// Paměť role u jedné karty: co role umí napříč projekty, co ví o tomhle projektu a co si k téhle
// kartě výslovně půjčila jinde. Panel je rodič svého kousku plochy — drží `useAgentMemory`, dotaz
// a složení pohledu; položky kreslí `AgentMemoryItem`, zápis a půjčku obsluhuje `AgentMemoryActions`.
// Roli karty panel neukládá sám: ohlásí ji callbackem nahoru (`onRoleChange`), protože `agentRole`
// je pole uzlu a ukládá ho ten, kdo drží stav Desktop v3 a jeho revizi. Nic se nečte ani nezapisuje
// samo — brief dá výchozí seznam, zbytek se stane teprve po stisku tlačítka.
import { useMemo, useState } from "react";
import {
  MAX_MEMORY_QUERY,
  NEEDS_PROVISIONING_BANNER,
  NO_ROLE_LABEL,
  briefRoleMemory,
  canRecall,
  memoryModel,
  memoryQuery,
  missingRoleLabels,
  provisionSummary,
  roleOptions,
  type LendDraft,
  type MemoryGroup,
  type RememberDraft,
} from "@/editor/node-detail/agent-workspace/memory/logic/agent-memory";
import { useAgentMemory } from "@/editor/node-detail/agent-workspace/memory/logic/use-agent-memory";
import AgentMemoryActions from "@/editor/node-detail/agent-workspace/memory/components/AgentMemoryActions";
import AgentMemoryItem from "@/editor/node-detail/agent-workspace/memory/components/AgentMemoryItem";
import type { NodeBrief } from "@/shared/desktop-state/logic/types";
import "@/editor/node-detail/agent-workspace/memory/styles/agent-memory.css";

const DISABLED_BANNER = "Paměť rolí je vypnutá. Zapni ji v Nastavení → Napojení.";

export default function AgentMemoryPanel({
  project, workspace, nodeId, readOnly, brief, agentRole, onRoleChange,
}: {
  project: string;
  workspace: string;
  nodeId: string;
  /** Uzavřená karta nebo main jen ke čtení: role se nepřepíná a do paměti se nezapisuje. */
  readOnly: boolean;
  /** Už načtený balíček karty; jeho `context.roleMemory` je výchozí seznam, nic se kvůli němu nevolá. */
  brief: NodeBrief | null;
  agentRole: string | null;
  /** Uloží roli na uzel ten, kdo drží stav a revizi; panel jen hlásí, co člověk vybral. */
  onRoleChange?: (role: string | null) => void;
}) {
  const seed = useMemo(() => briefRoleMemory(brief), [brief]);
  const feed = useAgentMemory({ project, workspace, nodeId }, agentRole, seed);
  const [query, setQuery] = useState("");
  const view = memoryModel(feed.status, feed.recall, feed.roles);
  const lentGroups = memoryModel(feed.status, feed.lent, feed.roles).groups;
  const fromBrief = feed.recall !== null && !feed.queried;
  const id = `agent-memory-${nodeId}`;
  const question = memoryQuery(brief, nodeId, query);

  const groups = (list: MemoryGroup[]) => list.map((group) => (
    <section key={group.id} className="agent-memory__group" aria-label={group.label}>
      <h4 className="agent-memory__group-title">{group.label}</h4>
      <ul className="agent-memory__list">
        {group.items.map((item) => <AgentMemoryItem key={item.uri} item={item} />)}
      </ul>
    </section>
  ));

  return (
    <div className="agent-memory" data-testid={`agent-memory-${nodeId}`}>
      {feed.state === "disabled" && <p className="agent-memory__banner">{DISABLED_BANNER}</p>}
      {feed.state === "unavailable" && (
        <p className="agent-memory__banner agent-memory__banner--unavailable" role="alert">
          {feed.status?.reason || "OpenViking neodpověděl; paměť role teď není k dispozici."}
          {feed.status?.url ? ` (${feed.status.url})` : ""}
        </p>
      )}
      {feed.state === "needs_provisioning" && (
        <div className="agent-memory__banner agent-memory__banner--needs-provisioning" role="alert">
          <p>{NEEDS_PROVISIONING_BANNER}</p>
          {missingRoleLabels(feed.status, feed.roles).length > 0 && (
            <p className="agent-memory__note">Chybí: {missingRoleLabels(feed.status, feed.roles).join(", ")}.</p>
          )}
          <button
            type="button" className="nodrag"
            disabled={feed.provisioning}
            onClick={() => void feed.provision()}
          >
            {feed.provisioning ? "Zakládám…" : "Založit klíče rolí"}
          </button>
          {feed.provisionResult && <p className="agent-memory__note">{provisionSummary(feed.provisionResult, feed.roles)}</p>}
        </div>
      )}
      {feed.state === "unknown" && (
        <p className="agent-memory__banner">
          {feed.loading ? "Zjišťuji stav paměti rolí…" : feed.error || "Stav paměti rolí se nepodařilo přečíst."}
        </p>
      )}
      {feed.error && feed.state !== "unknown" && <p className="agent-memory__banner agent-memory__banner--unavailable" role="alert">{feed.error}</p>}

      <label className="agent-memory__role" htmlFor={`${id}-role`}>
        Role karty
        <select
          id={`${id}-role`} value={agentRole ?? ""} disabled={readOnly || !onRoleChange}
          onChange={(event) => onRoleChange?.(event.target.value || null)}
        >
          {roleOptions(feed.roles).map((option) => (
            <option key={option.value || "none"} value={option.value}>{option.label}</option>
          ))}
        </select>
      </label>
      {!agentRole && <p className="agent-memory__note">{NO_ROLE_LABEL}: paměť se bez ní nečte ani nezapisuje.</p>}
      {view.state === "skipped" && view.reason && <p className="agent-memory__note">{view.reason}</p>}

      <div className="agent-memory__recall">
        <label htmlFor={`${id}-query`}>
          Dotaz
          <input
            id={`${id}-query`} maxLength={MAX_MEMORY_QUERY} value={query}
            placeholder="Prázdné = cíl karty"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <button
          type="button" className="nodrag"
          disabled={feed.busy || !canRecall(agentRole, question, feed.state)}
          onClick={() => void feed.recallNow(question)}
        >
          {feed.busy ? "Vybavuji…" : "Vybavit"}
        </button>
      </div>

      {fromBrief && !view.empty && <p className="agent-memory__note">Zatím z briefu karty; „Vybavit“ se zeptá znovu.</p>}
      {view.truncated && <p className="agent-memory__note">Výsledek je oříznutý rozpočtem tokenů.</p>}
      {groups(view.groups)}
      {feed.recall && view.empty && feed.state === "configured" && view.state !== "skipped" && (
        <p className="agent-memory__note">Role si k tomuhle dotazu nic nevybavila.</p>
      )}
      {groups(lentGroups)}

      <AgentMemoryActions
        nodeId={nodeId} role={agentRole} roles={feed.roles} state={feed.state}
        readOnly={readOnly} busy={feed.busy} saved={feed.saved}
        onRemember={(draft: RememberDraft) => feed.remember(draft, readOnly)}
        onLend={(draft: LendDraft) => feed.lend(draft)}
      />
    </div>
  );
}
