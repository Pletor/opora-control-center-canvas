// Čtení a zápis pohledu „Požadavky a plán“. Čte `GET /api/intake`, rozhodnutí o návrhu milníku posílá
// `POST /api/intake/milestone` sdíleným klientem `api` (cookie člověka `opora_ui`, stejný Origin, 428 obnoví relaci).
// Rozhodnutí o milníku smí jen člověk; zápis se po odmítnutí neopakuje.
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
