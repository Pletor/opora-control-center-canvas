// Stopa fragmentu v jeho detailu: ukáže platnou stopu a zda je vlastní, nebo zděděná, a umí ji přeřadit
// (`op: set-track`, nová revize se stejným textem, CAS přes poslední revizi ze stromu). Přeřazení přesune
// i podstrom, který stopu dědí. Nová stopa se ohlásí nahoru, aby fragment zůstal v pohledu.
import { useState } from "react";
import type { Track, VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { vaultOp, type VaultScope } from "../logic/vault-actions";
import { trackLabel, viewOf } from "../logic/vault-tracks";

type Choice = Track | "inherit";

export default function TrackReassign({ scope, fragment, readOnly, onMoved }: {
  scope: VaultScope;
  /** Fragment z načteného stromu (nese poslední revizi a stopu); chybí = mimo rozsah. */
  fragment: VaultNode | undefined;
  readOnly: boolean;
  onMoved: (track: Track) => void;
}) {
  const [choice, setChoice] = useState<Choice | "">("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  if (!fragment) return null;
  const view = viewOf(fragment);
  const own = fragment.track != null;
  const how = view === "none" ? "" : own ? " · vlastní" : " · zděděná";
  async function move(next: Choice) {
    const track = next === "inherit" ? null : next;
    setBusy(true); setMessage("");
    try {
      await vaultOp(scope, { op: "set-track", fragmentId: fragment!.id, expectedRevision: fragment!.revision, track,
        note: track ? `Přeřazeno do stopy ${trackLabel(track)}.` : "Stopa se dědí po předkovi." });
      setChoice("");
      if (track) onMoved(track);
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <div className="vault-actions vault-dock__track-of" data-testid="vault-fragment-track">
      <span className="vault-pill">Stopa: {trackLabel(view)}{how}</span>
      {!readOnly && (
        <>
          <select aria-label="Přeřadit do stopy" value={choice} disabled={busy} onChange={(event) => setChoice(event.target.value as Choice)}>
            <option value="">Přeřadit do…</option>
            <option value="ux" disabled={own && fragment.track === "ux"}>CX/UX/UI</option>
            <option value="logic" disabled={own && fragment.track === "logic"}>Backend + DB</option>
            {fragment.parentId && own && <option value="inherit">dědit po předkovi</option>}
          </select>
          <button type="button" className="vault-button" disabled={busy || !choice} onClick={() => choice && void move(choice)}>Přeřadit</button>
        </>
      )}
      {message && <span className="vault-dock__error" role="alert">{message}</span>}
    </div>
  );
}
