// Pohled vrstvy 1 (Layout | Design) v adrese `look=design`, aby přežil obnovení i návrat z plátna logiky.
import { useEffect, useState } from "react";
import { lookOf, withLookParam, type Look } from "./design-look";

export function useLook(): [Look, (look: Look) => void] {
  const [look, setLook] = useState<Look>(() => lookOf(location.search));
  useEffect(() => { history.replaceState(history.state, "", "/?" + withLookParam(location.search, look)); }, [look]);
  return [look, setLook];
}
