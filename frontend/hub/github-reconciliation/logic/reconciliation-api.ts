/** Human browser session first; uncertain writes are never automatically replayed. */
export async function postReconciliation<T>(url: string, payload: object, transport: typeof fetch = fetch): Promise<T> {
  const session = await transport("/api/access/ui-session", { cache: "no-store" });
  if (!session.ok) throw new Error("Lidskou relaci prohlížeče se nepodařilo ověřit.");
  const response = await transport(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) {
    const data = await response.json().catch(() => null) as { error?: unknown; detail?: unknown } | null;
    const reason = data?.error ?? data?.detail;
    throw new Error(typeof reason === "string" ? reason : `Sledování odmítnuto (HTTP ${response.status}).`);
  }
  return response.json() as Promise<T>;
}
