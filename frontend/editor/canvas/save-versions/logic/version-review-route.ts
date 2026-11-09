/** A history link selects one immutable version only inside its explicit scope. */
export function reviewVersion(search: string, project: string, workspace: string): string | null {
  const q = new URLSearchParams(search);
  const id = q.get("canvasVersion");
  return q.get("project") === project && q.get("workspace") === workspace && id && /^[a-f0-9]{32}$/.test(id) ? id : null;
}
