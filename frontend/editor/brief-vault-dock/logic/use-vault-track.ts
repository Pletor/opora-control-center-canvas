// Vazba přepínače stop na React: drží poslední volbu (nebo `null`, dokud člověk nevybral) a ukládá ji
// jednou pro aplikaci pod `opora:vault-track:v1`. Pravidla jsou ve `vault-tracks.ts`.
import { useCallback, useState } from "react";
import { readTrack, writeTrack, type TrackView } from "./vault-tracks";

export function useVaultTrack(): [TrackView | null, (track: TrackView) => void] {
  const [track, setTrack] = useState<TrackView | null>(readTrack);
  const choose = useCallback((next: TrackView) => { setTrack(next); writeTrack(next); }, []);
  return [track, choose];
}
