import type { ActionRequest } from "./linie-actions";
import type { BoardBall, Worktree } from "./linie-board";
import { trialOf, type Trial } from "./linie-trial";
import { list, rec, str } from "./view-common";

/**
 * „Čeká na tebe“ (docs/navrhy/2026-11-06-linie-rebrand.md §6, §7 bod 7, L7g): seřazený seznam rozhodnutí člověka.
 * Pořadí, větu „začlení X do Y, pak bude na řadě Z“ i jedinou akci řádku počítá služba (`queues.human[]` boardu);
 * prohlížeč nic nepřeskládává, jen čte, skládá text ověření a trasu akce. Každé kliknutí nese nové `op`.
 */
export type HumanAction = { kind: "accept_merge"; label: string };
export type HumanRow = {
  ticketId: string; mark: string; title: string; branch: string; target: string; sha: string; order: number;
  state: string; next: string; sentence: string; checks: { state: string; sha: string }; trial: Trial; action: HumanAction | null;
};

const KINDS = ["accept_merge"];
const short = (sha: string) => sha.slice(0, 7);

/** `queues.human[]` ze syrového boardu; řádek bez `ticketId` nebo s neznámou akcí se zahodí / zůstane bez tlačítka. */
export function humanQueueView(raw: unknown): HumanRow[] {
  return list(rec(rec(raw).queues).human).map((item, index) => {
    const r = rec(item), c = rec(r.checks), a = rec(r.action);
    return {
      ticketId: str(r.ticketId), mark: str(r.mark), title: str(r.title), branch: str(r.branch), target: str(r.target), sha: str(r.sha),
      order: typeof r.order === "number" ? r.order : index + 1, state: str(r.state), next: str(r.next), sentence: str(r.sentence),
      checks: { state: str(c.state), sha: str(c.sha) }, trial: trialOf(r.trial),
      action: KINDS.includes(str(a.kind)) ? { kind: str(a.kind) as HumanAction["kind"], label: str(a.label) } : null,
    };
  }).filter((row) => row.ticketId);
}

const CHECKS: Record<string, string> = { passed: "kontroly prošly", failed: "kontroly selhaly", running: "kontroly běží", missing: "kontroly chybí" };

/** Co je ověřené kontrolami pro revizi; stav náhledu a zkoušky říká `trial` (linie-trial.ts). */
export function verified(row: HumanRow): string {
  return `${CHECKS[row.checks.state] ?? "kontroly: nevím"}${row.checks.sha ? ` ${short(row.checks.sha)}` : ""}`;
}

/**
 * Trasa jediné akce řádku; `op` = nové UUID na každé kliknutí (opakování téhož požadavku nic nezdvojí).
 * `untested` = člověk výslovně potvrdil „přijmout bez zkoušky“.
 */
export function humanRequest(row: HumanRow, op: string, untested = false): ActionRequest | null {
  const path = `/work/${encodeURIComponent(row.ticketId)}`;
  if (row.action?.kind === "accept_merge") return { path: `${path}/accept-merge`, body: { sha: row.sha, op, ...(untested ? { untested: true } : {}) }, method: "POST", done: `Začleněno ${row.branch} do ${row.target}.` };
  return null;
}

/** Vyzkoušet z řádku: `start` spustí náhled, `tried` zapíše, že člověk otevřel běžící náhled. */
export function trialRequest(row: HumanRow, kind: "start" | "tried"): ActionRequest {
  const path = `/work/${encodeURIComponent(row.ticketId)}`;
  return kind === "start" ? { path: `${path}/preview`, body: {}, method: "POST", done: "Náhled se spouští." }
    : { path: `${path}/tried`, body: {}, method: "POST", done: `Zkouška zapsána na ${short(row.trial.sha)}.` };
}

/** Prázdný stav: kdo teď pracuje – agenti s živou vazbou na worktree, jinak kuličky v práci. */
export function idleText(balls: Pick<BoardBall, "mark" | "title" | "judgement">[], worktrees: Pick<Worktree, "binding">[]): string {
  const agents = worktrees.flatMap((w) => (w.binding?.live && w.binding.agent ? [w.binding.agent] : []));
  const wip = balls.filter((b) => b.judgement.summary.key === "wip").map((b) => b.mark || b.title);
  const names = [...new Set([...agents, ...wip])];
  return `Nic nečeká na tebe. Pracují: ${names.length ? names.join(", ") : "nikdo"}.`;
}

/** Odmítnutí služby (409) větou a jedinou opravou z `hint`. */
export function refusalText(failure: unknown): string {
  const body = rec((failure as { body?: unknown } | null)?.body);
  const said = str(body.error) || (failure instanceof Error ? failure.message : "Akce selhala.");
  return str(body.hint) ? `${said} Oprava: ${str(body.hint)}` : said;
}
