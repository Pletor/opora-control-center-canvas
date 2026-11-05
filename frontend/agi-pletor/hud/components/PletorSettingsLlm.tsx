import "../styles/pletor-llm.css";
import { Fragment, type ReactNode } from "react";
import type { PletorLlm } from "../logic/llm-settings";
import PletorLlmAccounts from "./PletorLlmAccounts";

type Fact = [string, string | number | null];
type Props = { llm: PletorLlm | null; loading: boolean; error: string | null; onRefresh: () => void };

const yes = (on: boolean) => (on ? "ano" : "ne");
const names = (items: string[]) => (items.length ? items.join(", ") : "žádné");

function Card({ title, available, reason, hint, facts, children }: {
  title: string; available: boolean; reason: string | null; hint?: string | null; facts: Fact[]; children?: ReactNode;
}) {
  return (
    <section className={"pletor-llm__card" + (available ? "" : " pletor-llm__card--off")} aria-label={title}>
      <h4 className="pletor-llm__card-title">
        {title}<span className="pletor-llm__state">{available ? "dostupné" : "nedostupné"}</span>
      </h4>
      {reason && <p className="pletor-llm__reason">{reason}</p>}
      {hint && <code className="pletor-llm__hint">{hint}</code>}
      {facts.length > 0 && (
        <dl className="pletor-llm__facts">
          {facts.map(([name, value]) => (
            <Fragment key={name}>
              <dt className="pletor-llm__fact-name">{name}</dt>
              <dd className="pletor-llm__fact-value">{value ?? "—"}</dd>
            </Fragment>
          ))}
        </dl>
      )}
      {children}
    </section>
  );
}

/**
 * Záložka LLM v nastavení Pletora jen ke čtení (M1): Claude Code, Codex, Ollama a účty z přepínače cswap.
 * Data dodává panel (`llm`), „Obnovit“ hlásí nahoru; nic se tu nemění ani neukládá.
 */
export default function PletorSettingsLlm({ llm, loading, error, onRefresh }: Props) {
  const { claude, codex, ollama, cswap } = llm ?? {};
  return (
    <div className="pletor-llm" aria-busy={loading}>
      <div className="pletor-llm__head">
        <span className="pletor-llm__note">{loading ? "Čtu nastavení počítače…" : error ?? "Jen ke čtení: co na tomto počítači běží."}</span>
        <button type="button" className="pletor-llm__refresh" onClick={onRefresh} disabled={loading}>Obnovit</button>
      </div>
      {claude && (
        <Card title="Claude Code" available={claude.available} reason={claude.reason} facts={claude.available ? [
          ["verze", claude.version], ["model", claude.model ?? "výchozí"], ["oprávnění", claude.permissionsMode],
          ["háčky", claude.hooks], ["MCP", names(claude.mcp)], ["CLAUDE.md", yes(claude.claudeMd)], ["skills", claude.skills],
          ["přihlášení", yes(claude.loggedIn)],
        ] : []} />
      )}
      {codex && (
        <Card title="Codex" available={codex.available} reason={codex.reason} facts={codex.available ? [
          ["verze", codex.version], ["model", codex.model ?? "výchozí"], ["uvažování", codex.reasoning], ["schvalování", codex.approval],
          ["sandbox", codex.sandbox], ["MCP", names(codex.mcp)], ["přihlášení", yes(codex.loggedIn)],
        ] : []} />
      )}
      {ollama && (
        <Card title="Ollama" available={ollama.available} reason={ollama.reason} facts={[
          ["volná VRAM", ollama.vram ? `${ollama.vram.freeGb} GB z ${ollama.vram.totalGb} GB` : "bez GPU NVIDIA"],
          ["v GPU", ollama.loaded.length ? ollama.loaded.map((m) => `${m.name} (${m.vramGb} GB)`).join(", ") : "nic"],
          ["nainstalované", ollama.installed.length ? ollama.installed.map((m) => `${m.name} ${m.sizeGb} GB`).join(", ") : "žádné"],
        ]} />
      )}
      {cswap && (
        <Card title="Přepínač účtů (cswap)" available={cswap.available} reason={cswap.reason} hint={cswap.installHint} facts={[]}>
          {cswap.available && <PletorLlmAccounts accounts={cswap.accounts} />}
        </Card>
      )}
    </div>
  );
}
