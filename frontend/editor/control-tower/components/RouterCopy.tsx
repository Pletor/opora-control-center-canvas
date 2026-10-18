// „N čeká na router“ v dlaždici sektoru a tlačítko, které zkopíruje zadání pro router. Když schránka
// selže, ukáže zadání v poli ke ručnímu zkopírování (`useCopyText` ho označí).
import { useCopyText, COPY_FAILED_TEXT } from "@/shared/hooks/logic/use-copy-text";
import { routerPrompt } from "../logic/router-prompt";

type Props = { project: string; workspace: string; sectorId: string; sectorName: string; unrouted: number };

export default function RouterCopy(props: Props) {
  const { status, copy, fieldRef } = useCopyText();
  const prompt = routerPrompt(props);
  return (
    <div className="tower-router">
      <span className="tower-router__count">{props.unrouted} čeká na router</span>
      {prompt && <button type="button" className="tower-router__copy" onClick={() => void copy(prompt)}>Zadání pro router</button>}
      <span className="tower-router__status" role="status">{status === "copied" ? "Zkopírováno" : ""}</span>
      {status === "failed" && prompt && <>
        <span className="tower-router__error" role="alert">{COPY_FAILED_TEXT}</span>
        <textarea ref={fieldRef} className="tower-router__field" readOnly value={prompt} aria-label="Zadání pro router" autoFocus onFocus={(e) => e.currentTarget.select()} />
      </>}
    </div>
  );
}
