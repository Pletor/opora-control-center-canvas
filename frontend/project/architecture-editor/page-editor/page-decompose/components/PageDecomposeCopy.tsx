// Tlačítko „Kopírovat zadání rozkladu“ (docs/architektura-pro-agenty.md §5.2): zkopíruje hotové zadání pro agenta-rozkladače
// stránky do schránky. Nic neskládá, neukládá ani nespouští – zadání dostane od rodiče v `prompt`, agenta spouští člověk
// v terminálu se skillem. Bez zadání je tlačítko vypnuté a `problem` řekne proč. Kopírování a hlášky obstará sdílený
// `useCopyText`; když schránka selže, ukáže se pole se zadáním k ruční kopii.
import { COPY_FAILED_TEXT, useCopyText } from "@/shared/hooks/logic/use-copy-text";
import "../styles/page-decompose.css";

export default function PageDecomposeCopy({ pageId, prompt, problem, variant = "card" }: {
  pageId: string; prompt: string | null; problem: string | null;
  /** `card` = tichá akce v patě karty, `header` = tlačítko v hlavičce plátna 2. */
  variant?: "card" | "header";
}) {
  const { status, copy, fieldRef } = useCopyText();
  return <span className={`page-decompose page-decompose--${variant}`}>
    <button type="button" className="page-decompose__button" disabled={!prompt} title={problem ?? "Zadání pro agenta: rozložit stránku na komponenty a kroky"}
      data-testid={"page-decompose-copy-" + pageId} onClick={() => prompt && void copy(prompt)}>
      {status === "copied" ? "Zkopírováno" : "Kopírovat zadání rozkladu"}
    </button>
    {status === "failed" && prompt && <span className="page-decompose__fallback">
      <span className="page-decompose__alert" role="alert">{COPY_FAILED_TEXT}</span>
      <textarea ref={fieldRef} className="page-decompose__field" aria-label="Zadání pro agenta-rozkladače stránky" readOnly rows={6} value={prompt}
        autoFocus onFocus={(event) => event.currentTarget.select()}/>
    </span>}
    <span className="page-decompose__status" role="status">{status === "copied" ? "Zadání rozkladu je ve schránce" : ""}</span>
  </span>;
}
