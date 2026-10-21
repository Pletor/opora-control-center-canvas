/** Human identity first; uncertain mutations are never automatically retried. */
export async function postContent(url: string, payload: object, transport: typeof fetch = fetch): Promise<unknown> {
  const session = await transport("/api/access/ui-session", { cache: "no-store" });
  if (!session.ok) throw new Error("Identitu prohlížeče se nepodařilo ověřit.");
  const response = await transport(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const result = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof result?.error === "string" ? result.error : `Akce byla odmítnuta (HTTP ${response.status}).`);
  return result;
}
