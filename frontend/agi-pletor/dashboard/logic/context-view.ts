import { list, rec, str, unavailable } from "./view-common";

export type ContextView = { text: string; sections: { title: string; size: string; truncated: boolean }[]; problem: string };

/** Odpověď `GET /api/pletor/context` → řádky sekcí („znaků / strop“) a celý text podkladů. */
export function contextView(raw: unknown): ContextView {
  const root = rec(raw);
  const sections = list(root.sections).map((item) => {
    const section = rec(item);
    return { title: str(section.title), size: `${str(section.chars) || "0"} / ${str(section.cap) || "—"}`, truncated: section.truncated === true };
  });
  return { text: str(root.text), sections, problem: [unavailable(root.text), unavailable(root.sections)].filter(Boolean).join(" · ") };
}
