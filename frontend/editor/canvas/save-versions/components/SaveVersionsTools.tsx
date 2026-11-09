// Pravý konec lišty Editoru: ikonka Historie uložení a ULOŽIT, pod nimi panel verzí. Skládá dílky
// a drží jen to, jestli je panel otevřený. Data (verze, dirty, ukládání) i obě akce dostává od App,
// které drží stav plátna a po obnovení vymění pohled, stav Desktop v3 a historii Ctrl+Z.
import { useCallback, useEffect, useState } from "react";
import SaveButton from "@/editor/canvas/save-versions/components/SaveButton";
import SaveHistoryButton from "@/editor/canvas/save-versions/components/SaveHistoryButton";
import SaveHistoryPanel from "@/editor/canvas/save-versions/components/SaveHistoryPanel";
import { reviewVersion } from "../logic/version-review-route";
import type { CanvasVersion } from "../logic/save-versions";
import type { CanvasVersionsState } from "@/editor/canvas/save-versions/logic/use-canvas-versions";
import "@/editor/canvas/save-versions/styles/save-versions.css";

export default function SaveVersionsTools({ project, workspace, versions, disabled, onSave, onRestore, onPrepareRestore, onReloadExternal }: {
  project: string;
  workspace: string;
  versions: CanvasVersionsState;
  disabled: boolean;
  onSave: () => void;
  onRestore: (versionId: string) => Promise<void>;
  onPrepareRestore: (versionId: string) => Promise<void>;
  onReloadExternal: () => void;
}) {
  const target = reviewVersion(window.location.search, project, workspace);
  const [open, setOpen] = useState(!!target);
  const [review, setReview] = useState<{ version: CanvasVersion; graph: { nodes: { id: string; name?: string }[] } } | null>(null);
  const [reviewError, setReviewError] = useState("");
  useEffect(() => {
    if (!target) return;
    const controller = new AbortController();
    setOpen(true); setReview(null); setReviewError("");
    const q = new URLSearchParams({ project, workspace, versionId: target });
    void fetch(`/api/canvas-versions?${q}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("Vybraná verze není dostupná.");
      return response.json();
    }).then(value => { if (!controller.signal.aborted) setReview(value); })
      .catch(error => { if (!controller.signal.aborted) setReviewError(String(error)); });
    return () => controller.abort();
  }, [project, workspace, target]);
  const items = review && !versions.versions.some(item => item.id === review.version.id)
    ? [review.version, ...versions.versions] : versions.versions;
  const close = useCallback(() => setOpen(false), []);
  return (
    <div className="save-versions" role="group" aria-label="Uložené verze">
      <SaveHistoryButton open={open} onToggle={() => setOpen((value) => !value)} />
      <SaveButton dirty={versions.dirty} saving={versions.saving} disabled={disabled} onSave={onSave} />
      {versions.externalChanged && <button type="button" className="save-versions__external" onClick={onReloadExternal}>Změna mimo toto okno · načíst</button>}
      {open && (
        <SaveHistoryPanel initialSelected={target} reviewNodes={review?.graph.nodes} versions={items} loading={versions.loading} error={reviewError || versions.error}
          disabled={disabled || versions.saving} onRestore={onRestore} onPrepareRestore={onPrepareRestore} onClose={close} />
      )}
    </div>
  );
}
