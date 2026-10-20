/** Obtain browser identity first; an uncertain mutation is never automatically replayed. */
export async function postGraphProposal<T>(url: string, payload: object, transport: typeof fetch = fetch): Promise<T> {
  const session = await transport("/api/access/ui-session", { cache: "no-store" });
  if (!session.ok) throw new Error("Identitu prohlížeče se nepodařilo ověřit. Obnovte přihlášení a zkuste akci znovu.");
  const response = await transport(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) {
    const data = await response.json().catch(() => null) as { error?: unknown; detail?: unknown } | null;
    const explanation = data?.error ?? data?.detail;
    throw new Error(typeof explanation === "string" ? explanation : `Akce byla odmítnuta (HTTP ${response.status}).`);
  }
  return response.json() as Promise<T>;
}
