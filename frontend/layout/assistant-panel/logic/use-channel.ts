// Kanál panelu Srdce | Asistent (docs/brain-heart-channel.md §1). Volba se ukládá jednou pro aplikaci
// (`assistant-prefs`); dokud člověk nevolil, rozhodne brána projektu. Stav brány se načte při otevření
// panelu a po přepnutí projektu; zapnutí brány z kanálu Srdce jde přes `enableGate`. Volá ho jen AssistantPanel.
import { useCallback, useEffect, useState } from "react";
import { enableGate, fetchGateSetting } from "@/layout/heart-channel/logic/heart-api";
import { pickChannel, readPrefs, writePrefs, type PanelChannel } from "./assistant-prefs";

export type ChannelApi = {
  channel: PanelChannel;
  setChannel: (next: PanelChannel) => void;
  /** `null` = brána se ještě zjišťuje (nebo chybí projekt). */
  gateOn: boolean | null;
  turnGateOn: () => void;
  /** Proč se bránu nepodařilo zapnout (prázdné = bez chyby). */
  gateFailure: string;
};

export function useChannel(open: boolean, project: string): ChannelApi {
  const [stored, setStored] = useState<PanelChannel | null>(() => readPrefs().channel);
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
  const setChannel = useCallback((next: PanelChannel) => { setStored(next); writePrefs({ channel: next }); }, []);
  const turnGateOn = useCallback(() => {
    if (!project) return;
    setGateFailure("");
    enableGate(project)
      .then((on) => setGate({ project, on }))
      .catch((error) => setGateFailure(error instanceof Error ? error.message : String(error)));
  }, [project]);

  return { channel: pickChannel(stored, gateOn === true), setChannel, gateOn, turnGateOn, gateFailure };
}
