// Stav zanoření boxu v adrese (`boxId`), aby otevřený box přežil obnovení stránky. Změna stránky zanoření zruší; box,
// který na stránce není (smazaný, cizí odkaz), se tiše ignoruje a plátno ukáže layout.
import { useEffect, useRef, useState } from "react";
import type { LayoutSection } from "../../layout-canvas/logic/layout-grid";
import { withBoxParam } from "./box-focus";

export function useBoxFocus(pageId: string | null, sections: readonly LayoutSection[]) {
  const [id, setId] = useState<string | null>(() => new URLSearchParams(location.search).get("boxId"));
  // Jen skutečná změna stránky, ne první vykreslení: to by smazalo box obnovený z adresy.
  const page = useRef(pageId);
  useEffect(() => { if (page.current !== pageId) { page.current = pageId; setId(null); } }, [pageId]);
  const focused = id && sections.some((section) => section.id === id) ? id : null;
  useEffect(() => { history.replaceState(history.state, "", "/?" + withBoxParam(location.search, focused)); }, [focused]);
  return { id: focused, open: (next: string) => setId(next), close: () => setId(null) };
}
