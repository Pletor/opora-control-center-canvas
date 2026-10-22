// Cesty a řádky ze specu jsou text od agenta. Do odkazu se dostanou jen přes tuto bránu: relativní
// POSIX cesta bez `..`, disku a zpětných lomítek, repozitář z provenance na github.com a plná SHA.
// URL skládáme sami (https://github.com/<owner>/<repo>/blob/<sha>/<cesta>#L<od>-L<do>), nikdy ji nepřebíráme.
export type FileRef = { path: string; startLine?: number; endLine?: number; revision?: "head" | "base" };
export type Repo = { owner: string; name: string; host?: string };

const NAME = /^[A-Za-z0-9_.-]{1,100}$/;
const SHA = /^[0-9a-f]{40}$/;

/** Bezpečná cesta souboru, nebo null. */
export function safePath(path: unknown): string | null {
  if (typeof path !== "string" || !path || path.length > 500) return null;
  if (path.startsWith("/") || /^[A-Za-z]:/.test(path) || path.includes("\\") || /[\u0000-\u001f\u007f]/.test(path)) return null;
  const parts = path.split("/");
  if (parts.some(part => !part || part === "." || part === "..")) return null;
  return path;
}

const line = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0 ? Number(value) : null;

/** „src/a.ts:38–85“, „src/a.ts:12“ nebo jen cesta. */
export function fileLabel(file: FileRef): string {
  const start = line(file.startLine), end = line(file.endLine);
  if (!start) return file.path;
  return end && end !== start ? `${file.path}:${start}–${end}` : `${file.path}:${start}`;
}

/** Odkaz na řádky v GitHubu, nebo null, když cokoli z repozitáře, SHA nebo cesty nesedí. */
export function blobUrl(repo: Repo | null | undefined, sha: string | null | undefined, file: FileRef): string | null {
  const path = safePath(file.path);
  if (!repo || !path || !sha || !SHA.test(sha) || !NAME.test(repo.owner) || !NAME.test(repo.name)) return null;
  if (repo.host !== undefined && repo.host !== "github.com") return null;
  const start = line(file.startLine), end = line(file.endLine);
  const anchor = start ? `#L${start}${end && end > start ? `-L${end}` : ""}` : "";
  return `https://github.com/${repo.owner}/${repo.name}/blob/${sha}/${path.split("/").map(encodeURIComponent).join("/")}${anchor}`;
}
