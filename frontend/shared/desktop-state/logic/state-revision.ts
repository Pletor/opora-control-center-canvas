import type { StateResponse } from "./types";
export type ScopedSnapshot = { scope: string; value: StateResponse };
/** Shodná revize stejného scope nemění reference karet; přepnutí scope se nikdy neslévá. */
export function retainSnapshot(previous: ScopedSnapshot | null, scope: string, next: StateResponse): StateResponse {
  return previous?.scope === scope && previous.value.revision === next.revision && previous.value.readOnly === next.readOnly
    ? previous.value : next;
}
