import "../styles/pletor-llm.css";
import { Fragment, useState, type ReactNode } from "react";
import { CLAUDE_EFFORTS, codexEfforts, keepEffort, type LlmModel, type PletorLlm } from "../logic/llm-settings";
import { putPletorLlm } from "../logic/pletor-client";
import PletorLlmAccountCard from "./PletorLlmAccountCard";
import PletorEffortSelect from "./PletorEffortSelect";
import PletorLlmModelSelect from "./PletorLlmModelSelect";

type Fact = [string, ReactNode];
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
 * Záložka LLM v nastavení Pletora: Claude Code, Codex, Ollama jen ke čtení (M1) a účty z přepínačů cswap a codex-swap,
 * kde člověk přepíná a přidává účty přihlášením (M2a, M2b). Data dodává panel (`llm`); po každé změně účtu se znovu načtou (`onRefresh`).
 */
export default function PletorSettingsLlm({ llm, loading, error, onRefresh }: Props) {
  const { claude, codex, ollama, cswap, codexswap } = llm ?? {};
  const [writeError, setWriteError] = useState<string | null>(null);
  // Jediný zapisovač modelu v kartě: PUT a znovunačtení, aby výběr ukázal to, co je opravdu v souboru.
  const save = (target: "claude" | "codex", model: string, effort: string) => {
    setWriteError(null);
    putPletorLlm(target, { model, ...(target === "claude" ? { effort } : { reasoning: effort }) }).then(onRefresh, (e: unknown) => setWriteError(e instanceof Error ? e.message : "Uložení modelu selhalo."));
  };
  const levelsOf = (target: "claude" | "codex", models: (LlmModel & { reasoning?: string[] })[], model: string | null) => (target === "claude" ? CLAUDE_EFFORTS : codexEfforts(models, model));
  const pick = (target: "claude" | "codex", models: (LlmModel & { reasoning?: string[] })[], model: string | null, effort: string | null) =>
    <PletorLlmModelSelect models={models} value={model ?? ""} label={`Model ${target === "claude" ? "Claude Code" : "Codexu"}`}
      onChange={(id) => save(target, id, keepEffort(levelsOf(target, models, id), effort))} />;
  const pickEffort = (target: "claude" | "codex", models: (LlmModel & { reasoning?: string[] })[], model: string | null, effort: string | null) =>
    <PletorEffortSelect levels={levelsOf(target, models, model)} value={effort ?? ""} label={`Effort ${target === "claude" ? "Claude Code" : "Codexu"}`}
      onChange={(level) => save(target, model ?? "", level)} />;
  const accountNote = (text: string) => <p className="pletor-llm__note">{text}</p>;
  return (
    <div className="pletor-llm" aria-busy={loading}>
      <div className="pletor-llm__head">
        <span className="pletor-llm__note">{loading ? "Čtu nastavení počítače…" : writeError ?? error ?? "Co na tomto počítači běží; účty Claude Code a Codexu se dají přepnout a přidat."}</span>
        <button type="button" className="pletor-llm__refresh" onClick={onRefresh} disabled={loading}>Obnovit</button>
      </div>
      {claude && (
        <Card title="Claude Code" available={claude.available} reason={claude.reason} facts={claude.available ? [
          ["verze", claude.version], ["model", pick("claude", claude.models, claude.model, claude.effort)],
          ["effort", pickEffort("claude", [], claude.model, claude.effort)], ["oprávnění", claude.permissionsMode],
          ["háčky", claude.hooks], ["MCP", names(claude.mcp)], ["CLAUDE.md", yes(claude.claudeMd)], ["skills", claude.skills],
          ["přihlášení", yes(claude.loggedIn)],
        ] : []}>{claude.available && accountNote("výchozí model terminálu (modely aktivního účtu); Pletor a Srdce mají vlastní")}</Card>
      )}
      {codex && (
        <Card title="Codex" available={codex.available} reason={codex.reason} facts={codex.available ? [
          ["verze", codex.version], ["model", pick("codex", codex.models, codex.model, codex.reasoning)],
          ["effort", pickEffort("codex", codex.models, codex.model, codex.reasoning)], ["schvalování", codex.approval],
          ["sandbox", codex.sandbox], ["MCP", names(codex.mcp)], ["přihlášení", yes(codex.loggedIn)],
        ] : []}>{codex.available && accountNote("výchozí model Codexu v terminálu (modely aktivního účtu)")}</Card>
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
          {cswap.available && <PletorLlmAccountCard tool="cswap" accounts={cswap} onChanged={onRefresh} />}
        </Card>
      )}
      {codexswap && (
        <Card title="Účty Codex (codex-swap)" available={codexswap.available} reason={codexswap.reason} hint={codexswap.installHint} facts={[]}>
          {codexswap.available && <PletorLlmAccountCard tool="codex" accounts={codexswap} onChanged={onRefresh} />}
        </Card>
      )}
    </div>
  );
}
