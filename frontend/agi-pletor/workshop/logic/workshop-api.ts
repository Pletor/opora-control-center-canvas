import { api } from "@/shared/types/logic/types";

/** Volání Dílny (docs/navrhy/2026-11-05-dilna-skillu.md §3a, §5) a odolné čtení odpovědí: chybějící pole jsou prázdná. */

export type WorkshopSkill = { name: string; description: string; files: string[] };
export type WorkshopTool = { name: string; path: string; cases: number };
export type ToolSource = { name: string; code: string; cases: string };
export type MeasureFailure = { name: string; got: unknown; expected: unknown };
export type Measure = {
  name: string; passed: number; total: number; failed: MeasureFailure[]; durationMs: number; deterministic: boolean; error: string | null;
};

type Raw = Record<string, unknown>;
const obj = (value: unknown): Raw => (value && typeof value === "object" && !Array.isArray(value) ? value as Raw : {});
const str = (value: unknown) => (typeof value === "string" ? value : "");
const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0);
const list = (value: unknown) => (Array.isArray(value) ? value.map(obj) : []);
const named = (items: Raw[]) => items.filter((item) => str(item.name));

export const parseSkills = (value: unknown): WorkshopSkill[] => named(list(obj(value).skills)).map((s) => ({
  name: str(s.name), description: str(s.description),
  files: Array.isArray(s.files) ? s.files.filter((f): f is string => typeof f === "string") : [],
}));

export const parseTools = (value: unknown): WorkshopTool[] =>
  named(list(obj(value).tools)).map((t) => ({ name: str(t.name), path: str(t.path), cases: num(t.cases) }));

export function parseToolSource(value: unknown): ToolSource {
  const raw = obj(value);
  return { name: str(raw.name), code: str(raw.code), cases: str(raw.cases) };
}

export function parseMeasure(value: unknown): Measure {
  const raw = obj(value);
  return {
    name: str(raw.name), passed: num(raw.passed), total: num(raw.total), durationMs: num(raw.durationMs),
    deterministic: raw.deterministic === true, error: str(raw.error) || null,
    failed: list(raw.failed).map((f) => ({ name: str(f.name), got: f.got, expected: f.expected })),
  };
}

/** Odpověď „Vygenerovat“: nový nástroj (případy jako text do editoru) a jeho první měření. */
export function parseGenerated(value: unknown): { source: ToolSource; measure: Measure } {
  const raw = obj(value);
  return {
    source: { name: str(raw.name), code: str(raw.code), cases: `${JSON.stringify(raw.cases ?? [], null, 2)}\n` },
    measure: parseMeasure(raw.measure),
  };
}

const BASE = "/api/pletor/workshop";
const part = encodeURIComponent;

export const fetchSkills = () => api<unknown>(`${BASE}/skills`).then(parseSkills);
export const createSkill = (name: string) => api<unknown>(`${BASE}/skills`, { name });
export const fetchSkillFile = (name: string, path: string) =>
  api<unknown>(`${BASE}/skills/${part(name)}/file?path=${part(path)}`).then((v) => str(obj(v).content));
export const saveSkillFile = (name: string, path: string, content: string) =>
  api<unknown>(`${BASE}/skills/${part(name)}/file`, { path, content }, "PUT");

export const fetchTools = () => api<unknown>(`${BASE}/tools`).then(parseTools);
export const createTool = (name: string) => api<unknown>(`${BASE}/tools`, { name });
export const fetchTool = (name: string) => api<unknown>(`${BASE}/tools/${part(name)}`).then(parseToolSource);
export const saveTool = (name: string, code: string, cases: string) => api<unknown>(`${BASE}/tools/${part(name)}`, { code, cases }, "PUT");
export const measureTool = (name: string) => api<unknown>(`${BASE}/tools/${part(name)}/measure`, {}).then(parseMeasure);
export const generateTool = (name: string, intent: string) => api<unknown>(`${BASE}/tools/generate`, { name, intent }).then(parseGenerated);
