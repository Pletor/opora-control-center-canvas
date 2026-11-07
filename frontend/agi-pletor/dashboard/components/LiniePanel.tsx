import { splitActions, type PletorAction } from "../logic/linie-actions";
import { clip, type Board, type BoardBall } from "../logic/linie-board";
import type { Queue } from "../logic/linie-queues";
import { queueLines } from "../logic/linie-queues";
import type { HeartRequest } from "../logic/linie-requests";
import { feedText, hhmm, pletorVerdict, sourceAges } from "../logic/linie-summary";
import type { WorkDetail } from "../logic/linie-work";
import { followsOf } from "../logic/linie-closed";
import LinieCommit from "./LinieCommit";
import LinieDetail from "./LinieDetail";
import LiniePletor from "./LiniePletor";
import LinieTrace from "./LinieTrace";

type Props = {
  editor: boolean; board: Board; ball: BoardBall | undefined; picked: string; detail: WorkDetail | null; query: string;
  queueList: Queue[]; now: number; lastSuccessAt: number | null; boardError: string; requests: HeartRequest[] | null;
  actions: PletorAction[]; acceptNote: string; onAcceptNote: (note: string) => void; flash: string; onAct: (id: string) => void; onAsk: (text: string) => Promise<string>;
  trace: string; onTrace: (mark: string) => void; commit: string; onCommit: (sha: string) => void;
  cluster: { ticketId: string; title: string }[]; onPick: (id: string) => void; onClose: () => void; onDetail: (detail: WorkDetail | null) => void;
};

/**
 * Pravý sloupec: panel Pletora (výrok, stáří zdrojů, akce, Zadat srdci) a pod ním Cesta, commit nebo detail kuličky –
 * vždy jen jeden. Oba dílky mluví o téže revizi boardu; akce provádí rodič.
 */
export default function LiniePanel(p: Props) {
  const panel = p.trace ? (
    <LinieTrace mark={p.trace} query={p.query} onClose={() => p.onTrace("")}
      onPickTicket={(id) => { p.onTrace(""); p.onCommit(""); p.onPick(id); }} onPickCommit={(sha) => { p.onTrace(""); p.onCommit(sha); }} />
  ) : p.commit ? (
    <LinieCommit sha={p.commit} query={p.query} onClose={() => p.onCommit("")} onPickTicket={(id) => { p.onCommit(""); p.onPick(id); }} onPickTrace={p.onTrace} />
  ) : p.picked ? (
    <LinieDetail ticketId={p.picked} query={p.query} ball={p.ball ?? null} follows={followsOf(p.board.balls, p.ball)} cluster={p.cluster} revision={p.lastSuccessAt}
      actions={splitActions(p.actions, p.ball?.judgement.summary.key ?? "").rest} note={p.acceptNote} onNote={p.onAcceptNote} flash={p.flash} onAct={p.onAct} onClose={p.onClose} onPickTrace={p.onTrace} onPick={p.onPick} onLoad={p.onDetail} />
  ) : null;
  if (!p.editor && !panel) return null;
  const ball = p.ball;
  const { main } = splitActions(p.actions, ball?.judgement.summary.key ?? "");
  return (
    <aside className={`pletor-dashboard__linie-panel${panel ? "" : " pletor-dashboard__linie-panel--idle"}`}>
      {p.editor && (
        <LiniePletor lines={ball ? pletorVerdict(ball.mark || clip(ball.title), ball.judgement, p.board.snapshot, p.now) : queueLines(p.queueList, p.board.balls.length)}
          next={ball ? ball.judgement.summary.next || (p.detail?.ticketId === p.picked ? p.detail.next : "") : ""} builtAt={p.board.snapshot ? hhmm(p.board.snapshot.builtAt) : ""}
          ages={sourceAges(p.board.snapshot, p.now)} feed={feedText(p.lastSuccessAt, p.boardError, p.now)}
          actions={main} note={p.acceptNote} onNote={p.onAcceptNote} flash={p.flash} onAct={p.onAct} requests={p.requests} onAsk={p.onAsk} />
      )}
      {panel}
    </aside>
  );
}
