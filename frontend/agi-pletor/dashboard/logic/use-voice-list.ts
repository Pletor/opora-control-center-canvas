import { useEffect, useState } from "react";
import { fetchVoices, type ServerVoice } from "@/agi-pletor/hud/logic/tts-voices";

/** Hlasy serveru načtené jednou při zobrazení části; `null` = ještě se načítá, nedostupný server = prázdný seznam. */
export function useVoiceList(): ServerVoice[] | null {
  const [voices, setVoices] = useState<ServerVoice[] | null>(null);
  useEffect(() => {
    let alive = true;
    void fetchVoices(null).then((list) => { if (alive) setVoices(list); });
    return () => { alive = false; };
  }, []);
  return voices;
}
