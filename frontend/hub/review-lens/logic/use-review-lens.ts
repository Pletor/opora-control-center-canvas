import { useSyncExternalStore } from "react";
import { useUiSession } from "@/hub/oporahub-card-drawer/logic/use-card-data";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { lensUrl, parseLensRead, type LensRead } from "./lens-read";

export type LensState = { read: LensRead | null; busy: boolean; error: string; reload: () => void };

/** Lens karty: jedno čtení při otevření detailu a po „Obnovit“ (žádné pollování). */
export function useReviewLens(project: string, workspace: string, nodeId: string, enabled: boolean): LensState {
  const session = useUiSession();
  const url = enabled && session && project && workspace && nodeId ? lensUrl(project, workspace, nodeId) : null;
  const read = useHubRead(url, parseLensRead);
  return { read: read.data, busy: read.busy, error: read.error, reload: read.reload };
}

// Motiv aplikace (`<html data-theme>`, frontend/app/logic/desktop-appearance.ts): plátno se kreslí
// ve stejném motivu a překreslí se, když ho uživatel přepne.
function subscribeTheme(listener: () => void) {
  const observer = new MutationObserver(listener);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}
const readTheme = () => (document.documentElement.dataset.theme === "light" ? "light" : "dark") as "light" | "dark";

export function useAppTheme(): "light" | "dark" {
  return useSyncExternalStore(subscribeTheme, readTheme, () => "dark");
}
