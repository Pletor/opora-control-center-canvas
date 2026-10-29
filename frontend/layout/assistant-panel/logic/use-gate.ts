// Stav brány projektu pro kanál Srdce (docs/brain-heart-channel.md §1). Načte se při otevření panelu
// a po přepnutí projektu; zapnutí brány z kanálu jde přes `enableGate`. Volá ho jen AssistantPanel.
import { useCallback, useEffect, useState } from "react";
import { enableGate, fetchGateSetting } from "@/layout/heart-channel/logic/heart-api";

export type GateApi = {
  /** `null` = brána se ještě zjišťuje (nebo chybí projekt). */
  gateOn: boolean | null;
  turnGateOn: () => void;
  /** Proč se bránu nepodařilo zapnout (prázdné = bez chyby). */
  gateFailure: string;
};

export function useGate(open: boolean, project: string): GateApi {
  const [gate, setGate] = useState<{ project: string; on: boolean } | null>(null);
  const [gateFailure, setGateFailure] = useState("");

  useEffect(() => {
    if (!open || !project) return;
    let alive = true;
    fetchGateSetting(project)
      .then((on) => { if (alive) setGate({ project, on }); })
      .catch(() => { if (alive) setGate({ project, on: false }); });
    return () => { alive = false; };
  }, [open, project]);

  const gateOn = gate && gate.project === project ? gate.on : null;
  const turnGateOn = useCallback(() => {
    if (!project) return;
    setGateFailure("");
    enableGate(project)
      .then((on) => setGate({ project, on }))
      .catch((error) => setGateFailure(error instanceof Error ? error.message : String(error)));
  }, [project]);

  return { gateOn, turnGateOn, gateFailure };
}
