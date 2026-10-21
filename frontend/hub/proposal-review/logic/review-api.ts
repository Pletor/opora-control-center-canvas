/** Negotiate browser identity before exactly one explicit mutation; never replay uncertainty. */
export async function postReview(path: string, payload: object, transport: typeof fetch = fetch): Promise<unknown> {
  const session = await transport("/api/access/ui-session", { cache: "no-store" });
  if (!session.ok) throw new Error("Identitu review se nepodařilo ověřit.");
  const response = await transport(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const value = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof value?.error === "string" ? value.error : `Review bylo odmítnuto (HTTP ${response.status}).`);
  return value;
}
