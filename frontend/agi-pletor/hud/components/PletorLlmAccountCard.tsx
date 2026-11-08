import { useState } from "react";
import type { CswapLlm } from "../logic/llm-settings";
import { cancelAccountLogin, finishAccountLogin, startAccountLogin, switchAccount, type AccountTool } from "../logic/pletor-client";
import PletorLlmAccounts from "./PletorLlmAccounts";
import PletorLlmLogin, { type LoginStep } from "./PletorLlmLogin";

type Props = { tool: AccountTool; accounts: CswapLlm; onChanged: () => void };

/**
 * Obsah karty přepínače účtů (Claude Code přes cswap, Codex přes codex-swap): seznam s Přepnout, přidání přihlášením
 * a chyba poslední akce. Drží jen rozpracované přihlášení; po každé změně hlásí `onChanged`, data znovu načte rodič.
 */
export default function PletorLlmAccountCard({ tool, accounts, onChanged }: Props) {
  const [login, setLogin] = useState<LoginStep>(null);
  const [busy, setBusy] = useState(false);
  const [fail, setFail] = useState<string | null>(null);
  const act = <T,>(work: () => Promise<T>, done: (value: T) => void, refresh = true) => {
    setBusy(true); setFail(null);
    work().then((value) => { done(value); if (refresh) onChanged(); }, (reason: unknown) => setFail(reason instanceof Error ? reason.message : "Akce selhala."))
      .finally(() => setBusy(false));
  };
  return (
    <>
      <PletorLlmAccounts accounts={accounts.accounts} busy={busy} onSwitch={(slot) => act(() => switchAccount(tool, slot), () => undefined)} />
      <PletorLlmLogin login={login} busy={busy} managed={accounts.managed}
        onAdd={() => act(() => startAccountLogin(tool), setLogin, false)}
        onFinish={(code) => act(() => finishAccountLogin(tool, code), () => setLogin(null))}
        onCancel={() => act(() => cancelAccountLogin(tool), () => setLogin(null))} />
      {fail && <p className="pletor-llm__reason" role="alert">{fail}</p>}
    </>
  );
}
