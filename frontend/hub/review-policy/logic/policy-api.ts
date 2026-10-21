/** One identified mutation attempt. Never retry a rejected or uncertain write. */
export async function postPolicy<T>(url: string, payload: object, transport: typeof fetch = fetch): Promise<T> {
  const session = await transport("/api/access/ui-session", { cache: "no-store" });
  if (!session.ok) throw new Error("Nepodařilo se ověřit lidskou relaci prohlížeče.");
  const response = await transport(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) {
    const data = await response.json().catch(() => null) as { error?: unknown; detail?: unknown } | null;
    const reason = data?.error ?? data?.detail;
    throw new Error(typeof reason === "string" ? reason : `Zápis pravidel byl odmítnut (HTTP ${response.status}).`);
  }
  return response.json() as Promise<T>;
}
