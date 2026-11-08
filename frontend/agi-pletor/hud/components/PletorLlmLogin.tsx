import { useState } from "react";

import type { AccountLogin } from "../logic/pletor-client";

export type LoginStep = AccountLogin | null;
type Props = {
  login: LoginStep; busy: boolean; managed: boolean;
  onAdd: () => void; onFinish: (code: string) => void; onCancel: () => void;
};

/**
 * Přidání dalšího účtu (Claude Code nebo Codex): Přidat účet otevře na tomto počítači prohlížeč s přihlášením; člověk se přihlásí
 * jiným účtem a klikne Hotovo. Když stránka místo potvrzení ukáže kód, vloží ho do pole. Je-li přihlášený účet mimo
 * uložené (`managed` false), nabídne Uložit přihlášený účet. Codex místo toho dá kód (`userCode`), který se zadá
 * na stránce. Stav i volání drží rodič, dílek jen hlásí.
 */
export default function PletorLlmLogin({ login, busy, managed, onAdd, onFinish, onCancel }: Props) {
  const [code, setCode] = useState("");
  if (!login) {
    return (
      <div className="pletor-llm__login-row">
        <button type="button" className="pletor-llm__refresh" onClick={onAdd} disabled={busy}>
          {busy ? "Pracuji…" : "Přidat účet"}
        </button>
        {!managed && (
          <button type="button" className="pletor-llm__refresh" onClick={() => onFinish("")} disabled={busy}
            title="Přihlášený účet ještě není mezi uloženými">Uložit přihlášený účet</button>
        )}
      </div>
    );
  }
  return (
    <form className="pletor-llm__login" onSubmit={(event) => { event.preventDefault(); onFinish(code.trim()); }}>
      {login.userCode ? (
        <p className="pletor-llm__note">
          <a className="pletor-llm__link" href={login.url} target="_blank" rel="noopener noreferrer">Otevři přihlášení</a> (nejlépe
          v anonymním okně), přihlas se jiným účtem a zadej kód <b className="pletor-llm__user-code">{login.userCode}</b>. Pak klikni Hotovo.
        </p>
      ) : (
        <p className="pletor-llm__note">
          Na tomto počítači se otevřel prohlížeč s přihlášením (jinak <a className="pletor-llm__link" href={login.url}
            target="_blank" rel="noopener noreferrer">otevři odkaz</a>). Přihlas se jiným účtem a klikni Hotovo. Ukáže-li
          stránka kód, vlož ho nejdřív sem.
        </p>
      )}
      <div className="pletor-llm__login-row">
        <button type="submit" className="pletor-llm__refresh" disabled={busy}>{busy ? "Ukládám…" : "Hotovo, přihlásil jsem se"}</button>
        {!login.userCode && <input className="pletor-llm__code" value={code} onChange={(event) => setCode(event.target.value)} placeholder="kód ze stránky (jen když ho ukáže)"
          aria-label="Kód ze stránky přihlášení" autoComplete="off" spellCheck={false} disabled={busy} />}
        <button type="button" className="pletor-llm__refresh" onClick={onCancel} disabled={busy}>Zrušit</button>
      </div>
    </form>
  );
}
