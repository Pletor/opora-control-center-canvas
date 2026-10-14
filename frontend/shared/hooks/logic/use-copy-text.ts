// Jedno chování pro všechna tlačítka „Kopírovat zadání“: zápis do schránky v try/catch, úspěch na 2 s
// (pro `role="status"`), neúspěch trvale (pro `role="alert"`) a při neúspěchu označení textu v poli,
// ať ho člověk zkopíruje ručně. Čistá část `copyText` je bez Reactu a testovaná.
import { useEffect, useRef, useState } from "react";

export type CopyStatus = "idle" | "copied" | "failed";

export const COPIED_MS = 2000;
export const COPY_FAILED_TEXT = "Kopírování se nezdařilo, označ text a zkopíruj ručně";

type ClipboardLike = { writeText?: (text: string) => Promise<void> } | undefined | null;

/** Zapíše text do schránky; nedostupná schránka, výjimka i zamítnutí vrátí „failed“, nikdy nevyhodí. */
export async function copyText(clipboard: ClipboardLike, text: string): Promise<Exclude<CopyStatus, "idle">> {
  try {
    if (!clipboard?.writeText) return "failed";
    await clipboard.writeText(text);
    return "copied";
  } catch {
    return "failed";
  }
}

/** Hook pro dílek: `fieldRef` dej na textareu se zadáním, `copy(text)` na tlačítko, `status` do hlášek. */
export function useCopyText() {
  const [status, setStatus] = useState<CopyStatus>("idle");
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (status !== "copied") return;
    const timer = window.setTimeout(() => setStatus("idle"), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [status]);

  const copy = async (text: string) => {
    const result = await copyText(typeof navigator === "undefined" ? undefined : navigator.clipboard, text);
    setStatus(result);
    if (result === "failed") fieldRef.current?.select();
  };

  return { status, copy, fieldRef };
}
