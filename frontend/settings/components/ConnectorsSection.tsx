import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import {
  CONNECTOR_STATUS_LABEL,
  CONNECTORS,
  memoryConnector,
  memorySettingsPayload,
  provisionPayload,
  provisionResultSummary,
  type MemoryStatusResponse,
  type ProvisionResult,
} from "@/settings/logic/connectors";

/**
 * Seznam aplikací k napojení. Připravované konektory jsou zatím jen katalog; OpenViking (paměť rolí)
 * je živý — jeho stav se čte z `GET /api/memory/status` a přepínač volá `POST /api/memory/settings`
 * a hned potom stav načte znovu, takže v seznamu stojí odpověď serveru, ne přání klienta. Přepínač
 * je nastavení celé aplikace, nikdy jednoho projektu.
 */
export default function ConnectorsSection() {
  const [status, setStatus] = useState<MemoryStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [provisioning, setProvisioning] = useState(false);
  const [provisionResult, setProvisionResult] = useState<ProvisionResult | null>(null);
  const generation = useRef(0);

  const read = useCallback(async () => {
    const ticket = ++generation.current;
    try {
      const value = await api<MemoryStatusResponse>("/api/memory/status");
      if (ticket !== generation.current) return;
      setStatus(value);
      setError("");
    } catch (reason) {
      if (ticket !== generation.current) return;
      setStatus(null);
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void read();
    return () => { ++generation.current; };
  }, [read]);

  async function toggle(next: boolean) {
    if (saving) return;
    setSaving(true);
    try {
      // Odpověď přepnutí je nový stav, ale přečte se znovu: jen tak se ukáže i to, že server po
      // zapnutí neodpovídá (`unavailable`), místo aby se zapnutí tvářilo jako hotové napojení.
      await api<MemoryStatusResponse>("/api/memory/settings", memorySettingsPayload(next));
      await read();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSaving(false);
    }
  }

  /** Rozdá klíče rolím jen na výslovný klik a hned poté přečte stav znovu (`read`). */
  async function provision() {
    if (provisioning) return;
    setProvisioning(true);
    try {
      const value = await api<ProvisionResult>("/api/memory/provision", provisionPayload());
      setProvisionResult(value);
      await read();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setProvisioning(false);
    }
  }

  return (
    <section className="settings-section" aria-labelledby="connectors-title">
      <h3 id="connectors-title">Connectors</h3>
      <p className="muted">Aplikace, které Opora napojí. Napojení je vždy výslovné, nic se nespouští samo.</p>
      {error && <p className="connector-error" role="alert">{error}</p>}
      <ul className="connectors">
        {CONNECTORS.map((item) => {
          const live = item.status === "live" ? memoryConnector(status) : null;
          return (
            <li key={item.id} className="connector">
              <div className="connector-body">
                <strong>{item.name}</strong>
                <span>{live?.detail ? `${item.purpose} ${live.detail}` : item.purpose}</span>
                {live?.tone === "needs_provisioning" && live.missingRoles.length > 0 && (
                  <span>Chybí: {live.missingRoles.join(", ")}.</span>
                )}
                {live?.tone === "needs_provisioning" && provisionResult && (
                  <span>{provisionResultSummary(provisionResult)}</span>
                )}
              </div>
              <span className={"connector-status " + (live ? live.tone : item.status)}>
                {live ? live.label : CONNECTOR_STATUS_LABEL[item.status]}
              </span>
              {live ? (
                <div className="connector-actions">
                  {live.tone === "needs_provisioning" && (
                    <button
                      type="button"
                      disabled={provisioning}
                      title="Založit klíče rolí u OpenVikingu"
                      onClick={() => void provision()}
                    >
                      {provisioning ? "Zakládám…" : "Založit klíče rolí"}
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={saving || live.busy}
                    title={live.enabled ? "Vypnout paměť rolí pro celou aplikaci" : "Zapnout paměť rolí pro celou aplikaci"}
                    onClick={() => void toggle(live.next)}
                  >
                    {saving ? "Ukládám…" : live.action}
                  </button>
                </div>
              ) : (
                <button type="button" disabled={item.status !== "available"} title={item.status === "available" ? "Napojit" : "Napojení zatím není k dispozici"}>
                  Napojit
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
