// Editor modelu domény nad úložištěm S4 (`useStudioModel`, revize a konflikt 409): drží historii úprav (zpět / znovu),
// poslední uloženou verzi (neuloženo = obsah se liší) a důvod, proč uložení neprošlo kontrolou. Načtený model s jiným
// obsahem historii začne znovu; odpověď na vlastní uložení (stejný obsah) historii nechá. Revize se k modelu přidá
// až při uložení, takže zpět nikdy nevrátí starou revizi.
import { useCallback, useEffect, useRef, useState } from "react";
import { useStudioModel } from "../../model/logic/use-studio-model";
import type { EditModel } from "./model-edit";
import { commit, historyOf, redo, undo, type History } from "./model-history";
import { sameContent, saveProblem } from "./model-save";

export function useModelEditor(project: string, domain: string) {
  const store = useStudioModel(project, domain);
  const [history, setHistory] = useState<History<EditModel>>(() => historyOf(store.model));
  const [saved, setSaved] = useState<EditModel>(store.model);
  const [problem, setProblem] = useState("");
  const seen = useRef(store.model);

  useEffect(() => {
    if (store.status !== "ready" || store.model === seen.current) return;
    const incoming: EditModel = seen.current = store.model;
    setSaved(incoming);
    setHistory((current) => sameContent(current.present, incoming) ? current : historyOf(incoming));
  }, [store.model, store.status]);

  const apply = useCallback((change: (model: EditModel) => EditModel, mergeKey: string | null = null) => {
    setHistory((current) => commit(current, change(current.present), mergeKey));
    setProblem("");
  }, []);

  const save = useCallback(async () => {
    const next: EditModel = { ...history.present, domainId: domain, revision: store.model.revision };
    const reason = saveProblem(next);
    setProblem(reason ?? "");
    if (!reason) await store.save(next);
  }, [history.present, domain, store]);

  return {
    model: history.present, revision: store.model.revision, status: store.status, message: store.message, problem,
    dirty: !sameContent(history.present, saved), canUndo: history.past.length > 0, canRedo: history.future.length > 0,
    apply, save,
    undo: useCallback(() => setHistory(undo), []),
    redo: useCallback(() => setHistory(redo), []),
    reload: useCallback(() => { setProblem(""); store.reload(); }, [store]),
  };
}
