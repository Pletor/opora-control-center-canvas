import type { NextAction } from "../logic/card-header";

/** Patička: jediná další akce karty (z `cards[].nextActionId`), kdo ji dělá a proč případně stojí. */
export default function DrawerFooter({ action, onRefresh, busy }: { action: NextAction | null; onRefresh: () => void; busy: boolean }) {
  return <footer className="card-drawer__foot" data-oh-next-action={action?.id ?? ""} data-oh-verb={action?.verb ?? ""}
    data-oh-action-status={action?.status ?? "none"} data-oh-actor={action?.actor ?? ""} data-oh-block-reason={action?.blockReason ?? ""}>
    <div className="card-drawer__foot-text">
      {action ? <>
        <b>Další: {action.label}</b>
        <span className="card-drawer__foot-note">
          <span className={`card-drawer__actor card-drawer__actor--${action.actor}`}>{action.actor === "human" ? "člověk" : "agent"}</span>
          {action.status === "ready" ? " · připraveno" : ` · stojí: ${action.blockText}`}
          <code className="card-drawer__mono"> {action.method} {action.path}</code>
        </span>
      </> : <><b>Žádná další akce</b><span className="card-drawer__foot-note">Agent-state pro kartu nenabízí akci.</span></>}
    </div>
    <button type="button" className="card-drawer__button" onClick={onRefresh} disabled={busy}>{busy ? "Načítám…" : "Obnovit"}</button>
  </footer>;
}
