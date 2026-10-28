// Jediný zdroj plné autonomie agentů pro otevřený projekt: přečte `agentAutonomy` z `GET /api/project-settings`
// a přepínač uloží hned přes `POST /api/project-settings/agent-autonomy` (mimo revizi ostatního nastavení).
// Volá ho jen rodič (App); štítky a přepínač dostávají hotová data v props.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { AUTONOMY_OFF, AUTONOMY_WRITE_URL, autonomyReadUrl, autonomyWriteBody, readAutonomy, type AgentAutonomy } from "./agent-autonomy";

export type AgentAutonomyApi = {
  autonomy: AgentAutonomy;
  /** Stav ještě není načtený (přepínač je do té doby zamčený). */
  loading: boolean;
  saving: boolean;
  error: string;
  /** Zapne nebo vypne plnou autonomii; `true`, když server změnu přijal. */
  setFull: (full: boolean) => Promise<boolean>;
};

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function useAgentAutonomy(project: string): AgentAutonomyApi {
  const [autonomy, setAutonomy] = useState<AgentAutonomy>(AUTONOMY_OFF);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const ticket = useRef(0);

  // Jiný projekt = jiný stav: štítek cizího projektu nesmí zůstat vidět ani chvíli.
  useEffect(() => {
    const current = ++ticket.current;
    setAutonomy(AUTONOMY_OFF); setLoading(true); setSaving(false); setError("");
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

  return { autonomy, loading, saving, error, setFull };
}
