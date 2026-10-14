import { useEffect, useState } from "react";
import "../styles/copy-id.css";

/**
 * Malý čip „ID“: plné ID je v `title`, klik ho zkopíruje do schránky a na 1,5 s ukáže „Zkopírováno“
 * (nebo „Nelze kopírovat“). Nic neukládá, takže smí žít v dílku bez callbacku nahoru.
 */
export default function CopyIdButton({ id, label = "ID" }: { id: string; label?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  useEffect(() => {
    if (state === "idle") return;
    const timer = window.setTimeout(() => setState("idle"), 1500);
    return () => window.clearTimeout(timer);
  }, [state]);
  const copy = () => { void navigator.clipboard.writeText(id).then(() => setState("copied"), () => setState("failed")); };
  return <button type="button" className={"copy-id" + (state !== "idle" ? " copy-id--" + state : "")} title={`${label}: ${id} (kliknutím zkopírujete)`}
    aria-label={`Kopírovat ${label} ${id}`} data-testid={"copy-id-" + id} onClick={(event) => { event.stopPropagation(); copy(); }}>
    {state === "copied" ? "Zkopírováno" : state === "failed" ? "Nelze kopírovat" : "ID"}
  </button>;
}
