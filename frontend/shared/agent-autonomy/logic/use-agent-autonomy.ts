// Jediný zdroj plné autonomie agentů pro otevřený projekt: přečte `agentAutonomy` z `GET /api/project-settings`
// a přepínač uloží hned přes `POST /api/project-settings/agent-autonomy` (mimo revizi ostatního nastavení).
// Volá ho jen rodič (App); štítky a přepínač dostávají hotová data v props.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { AUTONOMY_OFF, AUTONOMY_WRITE_URL, GATE_OFF, GATE_URL, autonomyReadUrl, autonomyWriteBody, gateReadUrl, gateWriteBody, readAutonomy, readGate, type AgentAutonomy, type BrainGate } from "./agent-autonomy";

export type AgentAutonomyApi = {
  autonomy: AgentAutonomy;
  /** Stav ještě není načtený (přepínač je do té doby zamčený). */
  loading: boolean;
  saving: boolean;
  error: string;
  /** Zapne nebo vypne plnou autonomii; `true`, když server změnu přijal. */
  setFull: (full: boolean) => Promise<boolean>;
  /** Brána mozku projektu; při zapnuté bráně ji autonomie projde jen s `passes` (docs/brain-gate.md §3). */
  gate: BrainGate;
  setPassesGate: (passes: boolean) => Promise<boolean>;
  /** Jeden přepínač velínu: plná autonomie i průchod bránou najednou (průchod platí i pro bránu zapnutou později). */
  setAutonomous: (on: boolean) => Promise<boolean>;
};

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function useAgentAutonomy(project: string): AgentAutonomyApi {
  const [autonomy, setAutonomy] = useState<AgentAutonomy>(AUTONOMY_OFF);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [gate, setGate] = useState<BrainGate>(GATE_OFF);
  const ticket = useRef(0);

  // Jiný projekt = jiný stav: štítek cizího projektu nesmí zůstat vidět ani chvíli.
  useEffect(() => {
    const current = ++ticket.current;
    setAutonomy(AUTONOMY_OFF); setGate(GATE_OFF); setLoading(true); setSaving(false); setError("");
    // Bránu čte kdokoli; chyba čtení nechá průchod vypnutý a přepínač průchodu se neukáže.
    api<unknown>(gateReadUrl(project)).then((value) => { if (current === ticket.current) setGate(readGate(value)); }).catch(() => undefined);
    api<unknown>(autonomyReadUrl(project))
      .then((value) => { if (current === ticket.current) setAutonomy(readAutonomy(value)); })
      .catch((reason) => { if (current === ticket.current) setError(message(reason)); })
      .finally(() => { if (current === ticket.current) setLoading(false); });
  }, [project]);

  const setFull = useCallback(async (full: boolean) => {
    const current = ++ticket.current;
    setSaving(true); setError("");
    try {
      const value = await api<unknown>(AUTONOMY_WRITE_URL, autonomyWriteBody(project, full));
      if (current === ticket.current) { setAutonomy(readAutonomy(value)); setLoading(false); }
      return true;
    } catch (reason) {
      if (current === ticket.current) setError(message(reason));
      return false;
    } finally {
      if (current === ticket.current) setSaving(false);
    }
  }, [project]);

  const setPassesGate = useCallback(async (passes: boolean) => {
    const current = ++ticket.current;
    setSaving(true); setError("");
    try {
      const value = await api<unknown>(GATE_URL, gateWriteBody(project, gate, passes));
      if (current === ticket.current) setGate(readGate(value));
      return true;
    } catch (reason) {
      if (current === ticket.current) setError(message(reason));
      return false;
    } finally {
      if (current === ticket.current) setSaving(false);
    }
  }, [project, gate]);

  const setAutonomous = useCallback(async (on: boolean) => (await setFull(on)) && (await setPassesGate(on)), [setFull, setPassesGate]);

  return { autonomy, loading, saving, error, setFull, gate, setPassesGate, setAutonomous };
}
