export type ProjectMapKind = "archify" | "graphify" | "architecture";
export function readProjectView(value: string | null): ProjectMapKind {
  return value === "graphify" || value === "architecture" ? value : "archify";
}
