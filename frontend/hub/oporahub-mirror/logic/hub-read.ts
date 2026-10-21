import { ACCESS_REQUIRED_EVENT } from "@/app/access-gate/logic/access-gate";

// Jednorázové čtení detailu OporaHubu: přísný parser, limit velikosti a 401 → brána přístupu.
// Zápisy jdou dál přes `api()` (lidská session); tady se jen čte.
export type Parse<T> = (raw: unknown) => T;
type Transport = (input: string, init: RequestInit) => Promise<Response>;
export const HUB_READ_LIMIT = 2 * 1024 * 1024;

export async function hubRead<T>(url: string, parse: Parse<T>, signal: AbortSignal,
  transport: Transport = (input, init) => fetch(input, init)): Promise<T> {
  const response = await transport(url, { signal, cache: "no-store", redirect: "error" });
  if (response.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event(ACCESS_REQUIRED_EVENT));
  if (!response.ok) throw new Error(`${url.split("?")[0]} není dostupné (HTTP ${response.status}).`);
  const raw = await response.text();
  if (raw.length > HUB_READ_LIMIT) throw new Error("Odpověď překročila povolenou velikost.");
  return parse(JSON.parse(raw));
}

/** JSON pro `<script type="application/json">`: `<` se escapuje, aby text nemohl ukončit značku. */
export function mirrorText(value: unknown) {
  return JSON.stringify(value ?? null).replace(/</g, "\\u003c");
}

export const isObject = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
export const isText = (value: unknown, max = 16000): value is string => typeof value === "string" && value.length <= max;
export const isCount = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0;
export const isNullableText = (value: unknown) => value === null || isText(value);
export const scopeQuery = (scope: Record<string, string>) => new URLSearchParams(scope).toString();
