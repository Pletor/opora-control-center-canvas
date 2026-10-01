// Dvě akce, které mění paměť nebo do ní sahají mimo tuhle kartu: „Zapamatovat“ (zápis do sdílené
// paměti role) a „Zapůjčit od role“ (dotaz do paměti někoho jiného). Obě stojí až pod výsledky,
// protože jsou to vědomé kroky, ne pokračování čtení. Dílek drží jen rozepsaný text a každé
// odeslání hlásí callbackem nahoru; o síť ani o stav se nestará. Zápis se nikdy nestane sám:
// tlačítko je jediná cesta a při zamčené kartě se formulář vůbec nekreslí.
import { useState } from "react";
import {
  MEMORY_KINDS,
  MEMORY_KIND_LABELS,
  MAX_MEMORY_QUERY,
  MAX_MEMORY_TEXT,
  canLend,
  canRemember,
  roleOptions,
  type LendDraft,
  type MemoryKind,
  type MemoryRole,
  type MemoryState,
  type RememberDraft,
} from "@/editor/node-detail/agent-workspace/memory/logic/agent-memory";

export default function AgentMemoryActions({
  nodeId, role, roles, state, readOnly, busy, saved, onRemember, onLend,
}: {
  nodeId: string;
  /** Role karty; bez ní nemá zápis kam jít a formulář se nenabízí. */
  role: string | null;
  roles: MemoryRole[];
  state: MemoryState;
  readOnly: boolean;
  busy: boolean;
  /** Adresa posledního uloženého zápisu; potvrzení, že server opravdu něco založil. */
  saved: string;
  onRemember: (draft: RememberDraft) => Promise<boolean>;
  onLend: (draft: LendDraft) => Promise<boolean>;
}) {
  const [kind, setKind] = useState<MemoryKind>("note");
  const [text, setText] = useState("");
  const [fromRole, setFromRole] = useState("");
  const [lendQuery, setLendQuery] = useState("");
  const id = `agent-memory-${nodeId}`;
  const draft: RememberDraft = { role, kind, text };
  const lendDraft: LendDraft = { fromRole, toRole: role ?? "", query: lendQuery };
  const lenders = roleOptions(roles).filter((option) => option.value && option.value !== role);

  async function remember() {
    if (!await onRemember(draft)) return;
    // Text mizí teprve po potvrzeném zápisu; při chybě zůstane rozepsaný k dalšímu pokusu.
    setText("");
  }

  return (
    <>
      {!readOnly && (
        <section className="agent-memory__form" aria-label="Zapamatovat do paměti role">
          <h4 className="agent-memory__form-title">Zapamatovat</h4>
          <p className="agent-memory__note">
            Zápis jde do sdílené paměti role, ne jen na tuhle kartu. Ukládá se až tlačítkem — nic se nezapisuje samo.
          </p>
          <label htmlFor={`${id}-kind`}>
            Druh
            <select id={`${id}-kind`} value={kind} onChange={(event) => setKind(event.target.value as MemoryKind)}>
              {MEMORY_KINDS.map((value) => <option key={value} value={value}>{MEMORY_KIND_LABELS[value]}</option>)}
            </select>
          </label>
          <label htmlFor={`${id}-text`}>
            Text
            <textarea
              id={`${id}-text`} rows={4} maxLength={MAX_MEMORY_TEXT} value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          <button
            type="button" className="nodrag"
            disabled={busy || !canRemember(draft, readOnly, state)}
            onClick={() => void remember()}
          >
            Zapamatovat pro roli
          </button>
          {saved && <p className="agent-memory__note">Uloženo jako <code>{saved}</code>.</p>}
        </section>
      )}

      <section className="agent-memory__form" aria-label="Zapůjčit paměť jiné role">
        <h4 className="agent-memory__form-title">Zapůjčit od role…</h4>
        <p className="agent-memory__note">
          Cizí zkušenost se vrací označená jako půjčka a nikdy se nemíchá s vlastní pamětí role.
        </p>
        <label htmlFor={`${id}-lender`}>
          Role
          <select id={`${id}-lender`} value={fromRole} onChange={(event) => setFromRole(event.target.value)}>
            <option value="">Vyberte roli</option>
            {lenders.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <label htmlFor={`${id}-lend-query`}>
          Dotaz
          <input
            id={`${id}-lend-query`} maxLength={MAX_MEMORY_QUERY} value={lendQuery}
            onChange={(event) => setLendQuery(event.target.value)}
          />
        </label>
        <button
          type="button" className="nodrag"
          disabled={busy || !canLend(lendDraft, state)}
          onClick={() => void onLend(lendDraft)}
        >
          Zapůjčit
        </button>
      </section>
    </>
  );
}
