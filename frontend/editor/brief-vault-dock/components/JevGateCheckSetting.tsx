// Nastavení v Přehledu Schránky: jednorázové povolení poradní kontroly bran přes Jev pro tento projekt
// (docs/schranka-neurony.md §7, §9 bod 10). Není to krok toku (kontrolu volají agenti přes API), jen souhlas
// člověka s odesíláním dat ven; povoluje jen člověk (POST /api/brain/jev/gate-check, agent dostane 403).
// Text předem jasně říká, co odejde: název, text, brána a payload fragmentu k poskytovateli.
import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { useVaultGet } from "../logic/vault-actions";
import { PROVIDER_LABELS, consentText, jevState, type JevPermission, type JevStatus } from "../logic/jev-check";

export default function JevGateCheckSetting({ project, readOnly }: { project: string; readOnly: boolean }) {
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const status = useVaultGet<JevStatus>("/api/brain/jev", null).data;
  const permission = useVaultGet<JevPermission>("/api/brain/jev/gate-check?" + new URLSearchParams({ project }), refresh).data;
  const state = jevState(status, permission);
  if (state === "unknown" || !status) return null;
  const provider = PROVIDER_LABELS[status.provider];
  async function set(allowed: boolean) {
    setBusy(true); setMessage("");
    try {
      await api("/api/brain/jev/gate-check", { project, provider: status!.provider, allowed });
      setRefresh((n) => n + 1);
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <section className="vault-panel vault-setting" aria-label="Nastavení: kontrola bran Jev" data-testid="jev-gate-check-setting">
      <h3 className="vault-panel__title">Nastavení: kontrola bran přes Jev ({provider})</h3>
      {state === "not-configured" ? (
        <p className="vault-panel__text">Není k dispozici: chybí klíč poskytovatele (nastavíš ho v Nastavení → Jev).</p>
      ) : (
        <>
          <p className="vault-panel__text">{consentText(status.provider)}</p>
          <label className="vault-setting__toggle">
            <input type="checkbox" checked={state === "allowed"} disabled={busy || readOnly} onChange={(event) => void set(event.target.checked)} />
            Povolit kontrolu bran Jev pro tento projekt
          </label>
        </>
      )}
      {message && <p className="vault-dock__error" role="alert">{message}</p>}
    </section>
  );
}
