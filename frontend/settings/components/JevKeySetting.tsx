import { useCallback, useEffect, useRef, useState } from "react";
import type { JevProvider, JevStatus } from "@/editor/brief-vault-dock/logic/jev-check";
import { jevKeyHint, jevKeyIsUsable, jevKeyPayload, jevKeyRows, parseJevStatus } from "@/settings/logic/jev-key";
import { api } from "@/shared/types/logic/types";

const STATUS_URL = "/api/brain/jev";
const KEY_URL = "/api/brain/jev/key";

/**
 * Klíče poskytovatelů Jev (TypeSafe, Celeris) pro celou aplikaci. Pole je maskované, po uložení se
 * vyprázdní a server vrací jen „nastavený / nenastavený“, takže se klíč nikdy neukáže zpátky.
 * Po každém zápisu se znovu čte `GET /api/brain/jev`: v řádku stojí odpověď serveru, ne přání UI.
 */
export default function JevKeySetting() {
  const [status, setStatus] = useState<JevStatus | null>(null);
  const [drafts, setDrafts] = useState<Partial<Record<JevProvider, string>>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<JevProvider | null>(null);
  const generation = useRef(0);

  const read = useCallback(async () => {
    const ticket = ++generation.current;
    try {
      const value = parseJevStatus(await api<unknown>(STATUS_URL));
      if (ticket !== generation.current) return;
      setStatus(value);
      setError(value ? "" : "Server vrátil neznámý stav klíčů Jev.");
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

  async function write(provider: JevProvider, key: string | null) {
    if (busy) return;
    setBusy(provider);
    try {
      await api<unknown>(KEY_URL, jevKeyPayload(key, provider));
      setDrafts((current) => ({ ...current, [provider]: "" }));
      await read();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="jev-key">
      <h4 className="jev-key__title">Klíč Jev</h4>
      <p className="muted jev-key__note">
        Rozhodovací model Jev vrací jen typované odpovědi. Klíč platí pro celou aplikaci, ukládá se jen na tomto počítači
        a zpátky se nikdy neukáže. Změna platí bez restartu.
      </p>
      {status ? jevKeyRows(status).map((row) => {
        const draft = drafts[row.provider] ?? "";
        const hint = jevKeyHint(draft);
        const id = `jev-key-${row.provider}`;
        return (
          <form
            key={row.provider}
            className="jev-key__row"
            onSubmit={(event) => {
              event.preventDefault();
              if (jevKeyIsUsable(draft)) void write(row.provider, draft);
            }}
          >
            <div className="jev-key__head">
              <label htmlFor={id} className="jev-key__label">
                {row.label}{row.active && <span className="jev-key__active"> · aktivní</span>}
              </label>
              <span className={`jev-key__state jev-key__state--${row.configured ? "set" : "unset"}`}>{row.state}</span>
            </div>
            <div className="jev-key__controls">
              <input
                id={id}
                className="jev-key__input"
                type="password"
                autoComplete="off"
                spellCheck={false}
                placeholder={row.configured ? "Nový klíč nahradí uložený" : "Vložte klíč"}
                value={draft}
                disabled={busy !== null}
                onChange={(event) => setDrafts((current) => ({ ...current, [row.provider]: event.target.value }))}
              />
              <button type="submit" disabled={!jevKeyIsUsable(draft) || busy !== null}>
                {busy === row.provider ? "Ukládám…" : "Uložit"}
              </button>
              <button type="button" disabled={!row.configured || busy !== null} onClick={() => void write(row.provider, null)}>
                Smazat
              </button>
            </div>
            {hint && <span className="jev-key__hint">{hint}</span>}
          </form>
        );
      }) : !error && <p className="muted">Zjišťuji stav klíčů Jev…</p>}
      <p className="jev-key__footnote">
        Klíč z proměnné prostředí backendu (<code>TYPESAFE_API_KEY</code>, <code>CELERIS_API_KEY</code>) se ukáže jako
        nastavený a Smazat ho neodstraní.
      </p>
      {error && <span className="jev-key__error" role="alert">{error}</span>}
    </div>
  );
}
