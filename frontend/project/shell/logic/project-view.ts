export type ProjectMapKind = "graphify" | "architecture";
export function readProjectView(value: string | null): ProjectMapKind {
  return value === "graphify" ? value : "architecture";
}
