import { useEffect, useState } from "react";
import { fetchPletorLlm } from "@/agi-pletor/hud/logic/pletor-client";
import type { PletorLlm } from "@/agi-pletor/hud/logic/llm-settings";
import { settingsView } from "../logic/settings-view";
import SettingsModelForm from "./SettingsModelForm";

/**
 * Nastavení (V4): modely Claude Code a Codexu se dají přepsat (`PUT /api/pletor/llm/...`, záloha souboru před zápisem),
 * konektory a MCP servery jsou zatím jen čtení z `GET /api/pletor/llm`. Po uložení se stav načte znovu.
 */
export default function DashboardSettings() {
  const [llm, setLlm] = useState<PletorLlm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => fetchPletorLlm().then((data) => { setLlm(data); setError(null); }, (e: unknown) => setError(e instanceof Error ? e.message : "Načtení selhalo."));
  useEffect(() => { void load(); }, []);
  if (!llm) return error ? <p className="pletor-dashboard__error" role="alert">{error}</p> : <p className="pletor-dashboard__note" role="status">Načítám nastavení…</p>;
  const view = settingsView(llm);
  return (
    <>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      <h2 className="pletor-dashboard__group-title">Modely LLM</h2>
      <SettingsModelForm target="claude" title="Claude Code" row={view.claude} onSaved={load} />
      <SettingsModelForm target="codex" title="Codex" row={view.codex} onSaved={load} />
      <h2 className="pletor-dashboard__group-title">Konektory, MCP servery, GitHub</h2>
      {view.connectors.map((item) => (
        <p key={item.source} className="pletor-dashboard__note">{item.source}: {item.names.length ? item.names.join(", ") : "žádné MCP servery"}</p>
      ))}
      <p className="pletor-dashboard__note">Zápis konektorů přijde s obsahem složek connectors/, mcp_servers/, dev_github/.</p>
    </>
  );
}
