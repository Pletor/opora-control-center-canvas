import type { useModelEditor } from "../logic/use-model-editor";
import { counted } from "../logic/proposal-rows";

type Editor = Pick<ReturnType<typeof useModelEditor>, "status" | "message" | "problem" | "dirty" | "revision" | "canUndo" | "canRedo" | "undo" | "redo" | "save" | "reload">;

/** Lišta nad plátnem MODELu: doména a počty, zpět / znovu, stav uložení (neuloženo, uloženo s revizí, ukládám,
 * konflikt) a Uložit. Konflikt nebo chyba nabídne „Načíst znovu“ (zahodí neuložené úpravy); model, který neprošel
 * kontrolou, řekne proč. V doméně scénáře nabídne návrat na model domény architektury. Akce volá editor od rodiče. */
export default function ModelToolbar({ editor, domainName, nodes, edges, back }: { editor: Editor; domainName: string; nodes: number; edges: number;
  /** Ve modelové doméně scénáře: návrat na model domény architektury (`label` = její název). */
  back?: { label: string; onBack: () => void } }) {
  const { status, dirty, revision } = editor;
  const state = status === "loading" ? "Načítám model…" : status === "saving" ? "Ukládám…" : status === "conflict" ? "Konflikt: model mezitím uložil někdo jiný."
    : status === "error" ? `Chyba: ${editor.message}` : dirty ? "Neuloženo" : revision ? `Uloženo · r${revision}` : "Nový model, zatím neuložený";
  const tone = status === "conflict" || status === "error" ? "alert" : dirty ? "dirty" : "clean";
  return <div className="studio-model__toolbar" data-testid="studio-model-toolbar">
    {back && <button type="button" className="studio-model__tool studio-model__tool--text" data-testid="studio-model-back" onClick={back.onBack}
      title="Zpět na model domény architektury; doména scénáře zůstane uložená, jak jste ji uložili">← {back.label}</button>}
    <span className="studio-model__domain">{back ? "Modelová doména scénáře" : "Model domény"} <strong data-testid="studio-model-domain-name">{domainName}</strong><small className="studio-model__counts">{counted(nodes, ["komponenta", "komponenty", "komponent"])} · {counted(edges, ["vazba", "vazby", "vazeb"])}</small></span>
    <button type="button" className="studio-model__tool" onClick={editor.undo} disabled={!editor.canUndo} title="Zpět (Ctrl+Z)" aria-label="Zpět">↶</button>
    <button type="button" className="studio-model__tool" onClick={editor.redo} disabled={!editor.canRedo} title="Znovu (Ctrl+Shift+Z)" aria-label="Znovu">↷</button>
    <span className={"studio-model__state studio-model__state--" + tone} role="status" data-testid="studio-model-save-state">{state}</span>
    {(status === "conflict" || status === "error") && <button type="button" className="studio-model__tool studio-model__tool--text" data-testid="studio-model-reload" onClick={editor.reload}
      title="Načte uloženou verzi; neuložené úpravy se zahodí">Načíst znovu</button>}
    <button type="button" className="studio-model__save" data-testid="studio-model-save" onClick={() => void editor.save()}
      disabled={!dirty || status === "saving" || status === "loading"}>Uložit</button>
    {editor.problem && <p className="studio-model__problem" role="alert" data-testid="studio-model-problem">Model nejde uložit: {editor.problem}</p>}
  </div>;
}
