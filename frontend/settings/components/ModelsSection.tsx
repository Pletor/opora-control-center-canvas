import { useEffect, useState } from "react";
import { fetchPletorLlm } from "@/pletor/logic/pletor-client";
import type { PletorLlm } from "@/pletor/logic/llm-settings";
import PletorSettingsLlm from "@/pletor/components/PletorSettingsLlm";

/** Reuse the existing machine inventory; this does not change role-to-model assignments. */
export default function ModelsSection() {
  const [data, setData] = useState<PletorLlm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true); setError(null);
    fetchPletorLlm().then((value) => { if (alive) setData(value); }, (reason) => { if (alive) setError(String(reason)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [revision]);
  return <section className="settings-section"><h2>Modely a účty</h2><p className="muted">Dostupní poskytovatelé, modely a MCP na tomto počítači. Přehled je pouze ke čtení; nepřiřazuje modely rolím srdce.</p><PletorSettingsLlm llm={data} loading={loading} error={error} onRefresh={() => setRevision((value) => value + 1)} /></section>;
}
