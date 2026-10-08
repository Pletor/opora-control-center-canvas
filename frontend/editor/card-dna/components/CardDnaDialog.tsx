import { type KeyboardEvent, type ReactNode, useMemo, useRef, useState } from "react";
import "../styles/card-dna.css";
import { useDialogOpening } from "../logic/use-dialog-opening";
import { flushSaveScope, saveScopeEntries } from "@/shared/hooks/logic/save-coordinator";
import { createDraftGuard } from "../logic/draft-guard";
import { DraftTransitionContext } from "../logic/draft-transition";

export type CardDnaTab = "overview" | "spec" | "process" | "workflow" | "evidence" | "code" | "dna";
const tabs: { key: CardDnaTab; label: string }[] = [
  { key: "overview", label: "Přehled" }, { key: "spec", label: "Zadání" }, { key: "process", label: "Proces" },
  { key: "workflow", label: "Pipeline a workflow" }, { key: "evidence", label: "Důkazy a kontroly" },
  { key: "code", label: "Kód a verze" }, { key: "dna", label: "DNA" },
];

type Props = { origin?: HTMLElement | null; project?: string; workspace?: string; title: string; onClose: () => void; overview?: ReactNode; spec?: ReactNode; process?: ReactNode; workflow?: ReactNode; evidence?: ReactNode; code?: ReactNode; dna?: ReactNode; renderTab?: (tab: CardDnaTab, open: (tab: CardDnaTab) => void) => ReactNode };

/** Jeden odmountovaný dialog pro kartu: záložka je jediný mountovaný detail, aby plátno neneslo editory. */
export default function CardDnaDialog({ title, onClose, origin = null, project = "", workspace = "", ...content }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<CardDnaTab>("overview");
  const [error, setError] = useState("");
  const transition = useMemo(() => createDraftGuard({ entries: () => saveScopeEntries(project, workspace),
    flush: () => flushSaveScope(project, workspace), report: setError }), [project, workspace]);
  const close = () => { void transition(onClose); };
  const openTab = (next: CardDnaTab) => { if (next !== tab) void transition(() => setTab(next)); };
  useDialogOpening(dialog, origin, close);
  const navigate = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const key = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
    if (key === null) return;
    event.preventDefault();
    const target = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[key];
    void transition(() => { setTab(tabs[key].key); target?.focus(); });
  };
  return <DraftTransitionContext.Provider value={transition}><dialog ref={dialog} className="card-dna" aria-labelledby="card-dna-title" onCancel={(event) => { event.preventDefault(); close(); }}>
    <header className="card-dna__head"><h2 className="card-dna__title" id="card-dna-title">DNA karty · {title}</h2><button className="card-dna__close" type="button" aria-label="Zavřít DNA karty" onClick={close}>×</button></header>
    <div className="card-dna__tabs" role="tablist" aria-label="DNA karty">
      {tabs.map((item, index) => <button className="card-dna__tab" key={item.key} type="button" role="tab" id={`card-dna-tab-${item.key}`} aria-selected={tab === item.key}
        aria-controls={`card-dna-panel-${item.key}`} tabIndex={tab === item.key ? 0 : -1} onClick={() => openTab(item.key)} onKeyDown={(event) => navigate(event, index)}>{item.label}</button>)}
    </div>
    {error && <p className="card-dna__error" role="alert">{error} Zůstaňte ve formuláři a zvolte Uložit nebo Zrušit změny.</p>}
    <section id={`card-dna-panel-${tab}`} className="card-dna__panel" role="tabpanel" aria-labelledby={`card-dna-tab-${tab}`}>{content.renderTab ? content.renderTab(tab, openTab) : content[tab]}</section>
  </dialog></DraftTransitionContext.Provider>;
}
