// Opora vložená v <iframe> cizí lokální aplikace (opora.toml `[app] embed_origins`):
// Escape, který Opora sama neobsloužila, se předá rodiči, aby mohl zavřít své překrytí.
// Mimo rámec se nic neděje. Zprávu dostane jen původ z document.referrer; bez referreru nic.

export const EMBED_ESCAPE_MESSAGE = { type: "opora:escape" } as const;

type KeyLike = { key: string; defaultPrevented: boolean; isComposing?: boolean };
type ParentLike = { postMessage(message: unknown, targetOrigin: string): void };
export type EmbedWindow = {
  self: unknown;
  top: unknown;
  parent: ParentLike;
  addEventListener(type: "keydown", listener: (event: KeyLike) => void): void;
};

/** Původ rodiče z referreru; prázdný, neplatný nebo ne-HTTP referrer = žádný příjemce. */
export function parentOriginFrom(referrer: string): string | null {
  if (!referrer) return null;
  try {
    const url = new URL(referrer);
    return url.protocol === "http:" || url.protocol === "https:" ? url.origin : null;
  } catch {
    return null;
  }
}

/** Předat? Jen Escape bez preventDefault (dialog Opory, který ho obsloužil, si ho nechá). */
export function shouldForwardEscape(event: KeyLike): boolean {
  return event.key === "Escape" && !event.defaultPrevented && !event.isComposing;
}

/** Zapojí předávání jednou při startu aplikace. Vrací true, když běží v rámu a má komu posílat. */
export function installEmbedEscape(win: EmbedWindow, referrer: string): boolean {
  if (win.self === win.top) return false;
  const parentOrigin = parentOriginFrom(referrer);
  if (!parentOrigin) return false;
  win.addEventListener("keydown", (event) => {
    if (shouldForwardEscape(event)) win.parent.postMessage(EMBED_ESCAPE_MESSAGE, parentOrigin);
  });
  return true;
}
