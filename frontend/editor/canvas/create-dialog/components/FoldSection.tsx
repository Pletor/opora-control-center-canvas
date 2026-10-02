// Sbalitelná sekce pop-upu tvorby pro nepovinná pole („Zadání sektoru“, „Pro agenta“). Výchozí je
// sbalená, aby první pohled ukázal jen to, bez čeho karta nevznikne; v hlavičce sbalené sekce je
// vidět, co v ní už je vyplněné. Jen zobrazení, stav otevření drží prohlížeč (`<details>`).
import type { ReactNode } from "react";

export default function FoldSection({ title, summary, children }: { title: string; summary: string; children: ReactNode }) {
  return (
    <details className="create-dialog__fold">
      <summary className="create-dialog__fold-head">
        <span className="create-dialog__fold-title">{title}</span>
        {summary && <span className="create-dialog__fold-value">{summary}</span>}
      </summary>
      <div className="create-dialog__fold-body">{children}</div>
    </details>
  );
}
