import { useState, type FormEvent } from "react";

type Pending = { identityId: string; name: string; githubLogin: string; marker?: string };
type Props = {
  busy: boolean; hasOperator: boolean; pending: Pending[];
  onClaim: (name: string, githubLogin: string, operator: boolean) => Promise<boolean>;
  onVerify: (identityId: string, number: number) => Promise<boolean>;
};

/** Ověřovací řádek: jen na obrazovce člověka, bez data-oh-* atributů (nonce nesmí vidět agent). */
function MarkerLine({ marker }: { marker: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try { await navigator.clipboard?.writeText(marker); setCopied(true); } catch { setCopied(false); }
  }
  return <div className="oporahub-identity__marker">
    <code className="oporahub-identity__marker-line">{marker}</code>
    <button type="button" className="oporahub-identity__button" onClick={() => void copy()}>{copied ? "✓ Zkopírováno" : "Kopírovat řádek"}</button>
  </div>;
}

function VerifyForm({ item, busy, onVerify }: { item: Pending; busy: boolean; onVerify: Props["onVerify"] }) {
  const [number, setNumber] = useState("");
  const valid = /^[1-9]\d{0,8}$/.test(number);
  return <form className="oporahub-identity__verify" onSubmit={event => { event.preventDefault(); if (valid) void onVerify(item.identityId, Number(number)); }}>
    <label className="oporahub-identity__field">Číslo PR nebo issue s komentářem
      <input inputMode="numeric" value={number} onChange={event => setNumber(event.target.value.trim())} placeholder="např. 42" />
    </label>
    <button type="submit" className="oporahub-identity__button oporahub-identity__button--primary" disabled={busy || !valid}>Ověřit</button>
  </form>;
}

/** Nárok a ověření: 1) jméno a GitHub login, 2) řádek vložit jako komentář, 3) ověřit číslem PR/issue. */
export default function IdentityClaim({ busy, hasOperator, pending, onClaim, onVerify }: Props) {
  const [name, setName] = useState("");
  const [login, setLogin] = useState("");
  const [operator, setOperator] = useState(false);
  const valid = name.trim().length > 0 && /^[A-Za-z0-9][A-Za-z0-9-]{0,38}$/.test(login.trim());
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && await onClaim(name.trim(), login.trim(), operator)) { setName(""); setLogin(""); setOperator(false); }
  }
  return <section className="oporahub-identity__panel" aria-labelledby="oh-identity-claim">
    <h4 id="oh-identity-claim" className="oporahub-identity__subtitle">Nárokovat identitu</h4>
    <form className="oporahub-identity__claim" onSubmit={event => void submit(event)}>
      <label className="oporahub-identity__field">Jméno člověka<input value={name} onChange={event => setName(event.target.value)} maxLength={120} /></label>
      <label className="oporahub-identity__field">GitHub login<input value={login} onChange={event => setLogin(event.target.value)} maxLength={39} autoComplete="off" /></label>
      <label className="oporahub-identity__check"><input type="checkbox" checked={operator} disabled={hasOperator} onChange={event => setOperator(event.target.checked)} />
        Operátor (přijímá plány u tohoto Canvasu){hasOperator ? " · operátor už je nastaven" : ""}</label>
      <button type="submit" className="oporahub-identity__button oporahub-identity__button--primary" disabled={busy || !valid}>Nárokovat</button>
    </form>
    {pending.map(item => <article key={item.identityId} className="oporahub-identity__pending">
      <p className="oporahub-identity__step"><b>{item.name}</b> (@{item.githubLogin}): vložte tento řádek <b>jako samostatný řádek komentáře</b> do
        libovolného PR nebo issue v GitHub repozitáři projektu, a to ze svého účtu @{item.githubLogin}. Pak zadejte číslo PR/issue a ověřte.</p>
      {item.marker ? <MarkerLine marker={item.marker} /> : <p className="oporahub-identity__note">Řádek se zobrazí jen v lidské session.</p>}
      <VerifyForm item={item} busy={busy} onVerify={onVerify} />
    </article>)}
  </section>;
}
