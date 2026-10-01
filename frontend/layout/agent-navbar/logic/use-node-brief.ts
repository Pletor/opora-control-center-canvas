// Vazba záložky Agenti na `GET /api/desktop-v3/node-brief` přes společný klient aplikace
// (`shared/desktop-state/logic/api.ts`), stejně jako to dělá Kontext v knihovně uzlu. Hook jen
// čte: nic neukládá a nic modelu neodesílá. Načte se při změně karty (`nodeId`), projektu,
// pracovního prostoru nebo `refreshKey` — to je otisk plátna a revize plochy, takže panel ukazuje
// stejnou pravdu jako karta pod ním. Pozdní odpověď po přepnutí karty se zahodí (`generation`),
// aby v panelu nikdy nesvítilo zadání jiné karty.
import { useEffect, useRef, useState } from "react";
import { errorMessage, fetchNodeBrief } from "@/shared/desktop-state/logic/api";
import type { NodeBrief } from "@/shared/desktop-state/logic/types";

export type UseNodeBrief = {
  brief: NodeBrief | null;
  loading: boolean;
  error: string;
};

export function useNodeBrief(
  project: string,
  workspace: string,
  nodeId: string | null,
  refreshKey: string,
): UseNodeBrief {
  const [brief, setBrief] = useState<NodeBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);

  useEffect(() => {
    const ticket = ++generation.current;
    if (!nodeId) {
      // Bez vybrané karty není co ukazovat; panel si o tom napíše vlastní větu.
      setBrief(null);
      setError("");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    fetchNodeBrief(project, workspace, nodeId)
      .then((value) => {
        if (ticket !== generation.current) return;
        setBrief(value);
        setLoading(false);
      })
      .catch((e) => {
        if (ticket !== generation.current) return;
        setBrief(null);
        setError(errorMessage(e));
        setLoading(false);
      });
  }, [project, workspace, nodeId, refreshKey]);

  return { brief, loading, error };
}
