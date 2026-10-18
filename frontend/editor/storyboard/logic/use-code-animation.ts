// Kód animace pro editor: drží Worker (vzniká jen u storyboardu s `animation: "kod"`), načítá zdroj při každé změně
// `code.source`, předává workeru obrázky podkladů (ImageBitmap z načtených obrázků) a vrací AnimationDef, kterou se
// obnovuje při příchodu snímku. Chybu modulu nebo kreslení vrací jako text. Kód animace sám nic nenačítá: podklady
// dostává jen tudy, podle `assets[].id` (u nového podkladu bez id podle fileId).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CodeAnimationHost } from "./code-animation-host";
import { codeAnimation } from "./animations/code";
import type { AnimationDef } from "./animations";
import { CODE_ANIMATION, type Storyboard } from "./storyboard-model";

export type CodeAnimationState = { animation: AnimationDef | undefined; error: string; slowMs: number | null };
export type AssetSources = ReadonlyMap<string, HTMLImageElement>;

/** Podklady storyboardu, které mají načtený obrázek: `[id podkladu, obrázek]`; klíč = `id`, u neuloženého `fileId`. */
export function assetSources(board: Storyboard | null, images: AssetSources): [string, HTMLImageElement][] {
  return (board?.assets ?? []).flatMap((a) => { const image = images.get(a.fileId); return image ? [[a.id ?? a.fileId, image] as [string, HTMLImageElement]] : []; });
}

export function useCodeAnimation(board: Storyboard | null, images: AssetSources = new Map()): CodeAnimationState {
  const code = board?.animation === CODE_ANIMATION ? board.code : undefined;
  const source = code?.source;
  const enabled = code !== undefined;
  const [host, setHost] = useState<CodeAnimationHost | null>(null);
  const [loaded, setLoaded] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [slowMs, setSlowMs] = useState<number | null>(null);
  const [version, setVersion] = useState(0);
  const [assetsKey, setAssetsKey] = useState("");
  const frame = useRef(0);
  const wanted = (board?.assets ?? []).filter((a) => images.has(a.fileId)).map((a) => `${a.id ?? a.fileId}=${a.fileId}`).join("|");

  useEffect(() => {
    if (!enabled) return;
    const created = new CodeAnimationHost();
    created.onSlow = setSlowMs;
    setHost(created);
    return () => { created.dispose(); setHost(null); setLoaded(null); };
  }, [enabled]);
  useEffect(() => {
    if (!host || source === undefined) return;
    let live = true;
    setError(""); setSlowMs(null);
    host.load(source).then(() => { if (live) setLoaded(source); }, (e: Error) => { if (live) { setLoaded(null); setError(e.message); } });
    return () => { live = false; };
  }, [host, source]);
  // Obrázky podkladů: při každé změně množiny se vyrobí čerstvé ImageBitmap (přenos je workeru odevzdá) a snímky začnou znovu.
  useEffect(() => {
    if (!host) return;
    let live = true;
    const pairs = assetSources(board, images);
    Promise.all(pairs.map(async ([id, image]) => ({ id, bitmap: await createImageBitmap(image) })))
      .then((list) => { if (!live) { list.forEach((item) => item.bitmap.close()); return; } host.setAssets(list); setAssetsKey(wanted); })
      .catch((e: Error) => { if (live) setError("Podklad se nepodařilo převést na obrázek: " + e.message); });
    return () => { live = false; };
    // board a images jsou shrnuté ve `wanted`; jiné změny storyboardu bitmapy nepotřebují.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [host, wanted]);
  // Snímky chodí po jednom; překreslení se slučuje do jednoho za okamžik.
  const onFrame = useCallback(() => {
    if (frame.current) return;
    frame.current = requestAnimationFrame(() => { frame.current = 0; setVersion((v) => v + 1); });
  }, []);
  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const animation = useMemo(
    () => (code ? codeAnimation(code, host, { ready: host !== null && loaded === code.source, assetsKey, onFrame, onError: setError }) : undefined),
    // version: nový snímek dorazil, definice se obnoví, aby se plátna a náhledy překreslily.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [code, host, loaded, version, assetsKey, onFrame],
  );
  return { animation, error, slowMs };
}
