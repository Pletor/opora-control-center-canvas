import { usageTone, type CswapAccount } from "../logic/llm-settings";

function resetText(iso: string): string {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? iso : at.toLocaleString("cs-CZ", { weekday: "short", hour: "2-digit", minute: "2-digit" });
}

function UsageBar({ label, pct }: { label: string; pct: number | null }) {
  return (
    <div className="pletor-llm__usage">
      <span className="pletor-llm__usage-label">{label}</span>
      <span className={`pletor-llm__bar pletor-llm__bar--${usageTone(pct)}`} role="meter" aria-label={`Využití ${label}`}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct ?? undefined}>
        <span className="pletor-llm__fill" style={{ width: `${Math.min(100, Math.max(0, pct ?? 0))}%` }} />
      </span>
      <span className="pletor-llm__pct">{pct === null ? "?" : `${Math.round(pct)} %`}</span>
    </div>
  );
}

type Props = { accounts: CswapAccount[]; busy: boolean; onSwitch: (slot: number) => void };

/** Účty Claude Code z `cswap list`: maskovaný e-mail (alias před ním), pruhy využití 5h a 7d, aktivní účet zvýrazněný,
 *  u ostatních tlačítko Přepnout (hlásí slot nahoru). */
export default function PletorLlmAccounts({ accounts, busy, onSwitch }: Props) {
  if (!accounts.length) return <p className="pletor-llm__note">Žádné účty. Přidej první tlačítkem níže.</p>;
  return (
    <ul className="pletor-llm__accounts">
      {accounts.map((account) => (
        <li key={account.slot ?? account.label} className={"pletor-llm__account" + (account.active ? " pletor-llm__account--active" : "")}>
          <span className="pletor-llm__account-name">
            {account.slot !== null && `${account.slot}: `}{account.alias ?? account.label}
            {account.alias && <small className="pletor-llm__account-mail"> {account.label}</small>}
            {account.active && <b className="pletor-llm__account-active"> aktivní</b>}
            {!account.active && account.slot !== null && (
              <button type="button" className="pletor-llm__switch" onClick={() => onSwitch(account.slot!)} disabled={busy}>Přepnout</button>
            )}
          </span>
          <UsageBar label="5h" pct={account.usage5h} />
          <UsageBar label="7d" pct={account.usage7d} />
          {account.resetsAt && <span className="pletor-llm__note">reset {resetText(account.resetsAt)}</span>}
        </li>
      ))}
    </ul>
  );
}
