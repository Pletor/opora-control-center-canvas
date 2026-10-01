import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api } from "@/shared/types/logic/types";
import {
  ACCESS_REQUIRED_EVENT,
  LOCAL_STATUS,
  lockedOut,
  needsGate,
  statusFrom,
  tokenHint,
  tokenIsUsable,
  type AccessStatus,
} from "@/app/access-gate/logic/access-gate";
import "@/app/access-gate/styles/access-gate.css";

/**
 * Brána vzdáleného přístupu: doma se nikdy neukáže, přes tunel stojí před aplikací.
 * Rodič drží stav (status, rozepsaný token, chyba); dílek tu žádný není — je to celá obrazovka.
 */
export default function AccessGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AccessStatus | null>(null);
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setStatus(statusFrom(await api<unknown>("/api/access/status")));
    } catch {
      // Starší backend nebo výpadek: nezamykáme aplikaci, kterou nemáme čím odemknout.
      setStatus(LOCAL_STATUS);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const relock = () => {
      setStatus((current) => lockedOut(current));
      setError("Přístup vypršel. Přihlaste se znovu.");
    };
    window.addEventListener(ACCESS_REQUIRED_EVENT, relock);
    return () => window.removeEventListener(ACCESS_REQUIRED_EVENT, relock);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !tokenIsUsable(token)) return;
    setBusy(true);
    setError("");
    try {
      await api<{ ok: boolean }>("/api/access/login", { token: token.trim() });
      setToken("");
      await load();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Přihlášení se nezdařilo.");
    } finally {
      setBusy(false);
    }
  }

  if (status === null) return null;
  if (!needsGate(status)) return <>{children}</>;
  const hint = tokenHint(token);
  return (
    <div className="access-gate">
      <form className="access-gate__card" onSubmit={submit}>
        <p className="access-gate__eyebrow">Opora Control Center</p>
        <h1 className="access-gate__title">Vzdálený přístup</h1>
        <p className="access-gate__note">
          Aplikace běží na domácím počítači a ven vede tunelem <code>{status.host}</code>. Dál pustí jen
          přístupový token.
        </p>
        <label className="access-gate__label" htmlFor="access-gate-token">
          Přístupový token
        </label>
        <input
          id="access-gate-token"
          className="access-gate__input"
          type="password"
          autoComplete="current-password"
          autoFocus
          spellCheck={false}
          value={token}
          onChange={(event) => setToken(event.target.value)}
        />
        {hint ? <p className="access-gate__hint">{hint}</p> : null}
        {error ? (
          <p className="access-gate__error" role="alert">
            {error}
          </p>
        ) : null}
        <button className="access-gate__submit" type="submit" disabled={busy || !tokenIsUsable(token)}>
          {busy ? "Přihlašuji…" : "Přihlásit"}
        </button>
        <p className="access-gate__footnote">
          Token nikdy nevkládejte do příkazů ani logů. Kdo ho má, má plný přístup k projektům.
        </p>
      </form>
    </div>
  );
}
