// Čtení a zápis pohledu „Požadavky a plán“. Čte `GET /api/intake`, rozhodnutí o návrhu milníku posílá
// `POST /api/intake/milestone` sdíleným klientem `api` (cookie člověka `opora_ui`, stejný Origin, 428 obnoví relaci).
// Rozhodnutí o milníku a odpověď na výslech (`/api/intake/brief/answer`, `/brief/start`) smí jen člověk, nebo agent
// při plné autonomii; zápis se po odmítnutí neopakuje.
import { api } from "@/shared/types/logic/types";
import { parseIntake, type IntakeResponse } from "./intake-plan";

export type MilestoneAction = "activate" | "reject";
type Call = <T>(url: string, body?: object) => Promise<T>;

export const intakeUrl = (project: string, workspace: string) => `/api/intake?${new URLSearchParams({ project, workspace })}`;

export async function readIntake(project: string, workspace: string, call: Call = api): Promise<IntakeResponse> {
  return parseIntake(await call<unknown>(intakeUrl(project, workspace)));
}

export async function decideMilestone(project: string, workspace: string, milestoneId: string, action: MilestoneAction, call: Call = api) {
  return call<{ id: string; status: string; superseded: string | null }>("/api/intake/milestone", { project, workspace, milestoneId, action });
}

/** Česká věta pro chybu rozhodnutí; text serveru (už česky) se zachová. */
export function decisionError(action: MilestoneAction, error: unknown) {
  const verb = action === "activate" ? "aktivovat" : "zamítnout";
  const reason = error instanceof Error && error.message ? error.message : "neznámá chyba";
  return `Milník se nepodařilo ${verb}: ${reason}`;
}

export type BriefAnswerResult = { requirement: string; question: string; answer: string; accepted: boolean; status: string;
  open: number; missing: string[] };

/** Odpověď člověka na otázku výslechu (`POST /api/intake/brief/answer`); `answer` null = potvrdit doporučení srdce. */
export async function answerBrief(project: string, workspace: string, requirement: string, question: string, answer: string | null,
  call: Call = api) {
  const body = answer === null ? { project, workspace, requirement, question, accept: true } : { project, workspace, requirement, question, answer };
  return call<BriefAnswerResult>("/api/intake/brief/answer", body);
}

/** „Vyslechni mě k tomu“ (`POST /api/intake/brief/start`): spis `draft` a jedno probuzení srdce. */
export async function startBrief(project: string, workspace: string, requirement: string, call: Call = api) {
  return call<{ requirement: string; status: string }>("/api/intake/brief/start", { project, workspace, requirement });
}

/** Česká věta pro chybu odpovědi nebo spuštění výslechu; text serveru (už česky) se zachová. */
export function briefError(kind: "answer" | "start", error: unknown) {
  const reason = error instanceof Error && error.message ? error.message : "neznámá chyba";
  return kind === "answer" ? `Odpověď se nepodařilo odeslat: ${reason}` : `Výslech se nepodařilo spustit: ${reason}`;
}
