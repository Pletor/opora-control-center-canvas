import type { ReactNode } from "react";

/** Keep the workspace mounted so opening global settings never discards editor drafts. */
export default function SettingsSurface({ page, children }: { page: ReactNode; children: ReactNode }) {
  return <><div hidden={!!page} inert={!!page} style={{ display: page ? "none" : "contents" }}>{children}</div>{page}</>;
}
