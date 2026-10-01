export type NoticeKind = "project" | "checking" | "unavailable" | "failure";

/**
 * Oznámení místo konverzace, když není s kým mluvit: chybí projekt, zjišťuje se CLI, `claude` není
 * k dispozici nebo selhalo spojení. Vždy řekne, co se stalo a co má uživatel udělat.
 */
export default function PanelNotice({ kind, detail = "" }: { kind: NoticeKind; detail?: string }) {
  if (kind === "project") {
    return (
      <div className="assistant-panel__notice">
        <p className="assistant-panel__notice-title">Vyberte projekt</p>
        <p className="assistant-panel__notice-text">Asistent pracuje nad jedním projektem. Zvolte ho v horní liště a úkoly se objeví tady.</p>
      </div>
    );
  }
  if (kind === "checking") {
    return (
      <div className="assistant-panel__notice">
        <p className="assistant-panel__notice-text">Zjišťuji, jestli je Claude Code k dispozici…</p>
      </div>
    );
  }
  if (kind === "unavailable") {
    return (
      <div className="assistant-panel__notice" role="alert">
        <p className="assistant-panel__notice-title">Claude Code není připravený</p>
        <p className="assistant-panel__notice-text">
          Příkaz <code className="assistant-panel__notice-code">claude</code> není nainstalovaný nebo přihlášený. Otevřete terminál, spusťte
          {" "}<code className="assistant-panel__notice-code">claude</code> a přihlaste se svým předplatným. Potom asistenta zavřete a otevřete znovu.
        </p>
      </div>
    );
  }
  return (
    <div className="assistant-panel__notice" role="alert">
      <p className="assistant-panel__notice-title">Asistent není dostupný</p>
      <p className="assistant-panel__notice-text">{detail}</p>
    </div>
  );
}
