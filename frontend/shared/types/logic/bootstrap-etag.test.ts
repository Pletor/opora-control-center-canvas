// Bootstrap (projekty, úlohy, draft, paměť) se polluje každé 2,5 s. Server k němu posílá ETag;
// klient ho drží v paměti, posílá If-None-Match a 304 obslouží z uloženého těla. Stejný obsah
// pak `keepSame` nechá ve staré referenci, takže App se nepřekresluje.
import { afterEach, describe, expect, it, vi } from "vitest";
import { keepSame } from "@/shared/hooks/logic/same-response";
import { api, type Bootstrap } from "@/shared/types/logic/types";

const BODY = { draft: { id: "draft", name: "Koncept" }, projects: [{ id: "p1", name: "Opora" }], jobs: [], memory: { enabled: false, status: "disabled" } };

describe("bootstrap s ETagem", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("druhé kolo pošle If-None-Match a 304 vrátí poslední tělo", async () => {
    const replies = [
      new Response(JSON.stringify(BODY), { status: 200, headers: { ETag: '"b1"' } }),
      new Response(null, { status: 304, headers: { ETag: '"b1"' } }),
      new Response(JSON.stringify({ ...BODY, jobs: [{ id: "j1" }] }), { status: 200, headers: { ETag: '"b2"' } }),
      new Response(null, { status: 304, headers: { ETag: '"b2"' } }),
    ];
    const sent: Array<string | undefined> = [];
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      sent.push((init?.headers as Record<string, string>)["If-None-Match"]);
      return replies.shift()!;
    }));
    const first = await api<Bootstrap>("/api/bootstrap");
    const unchanged = await api<Bootstrap>("/api/bootstrap");
    expect(unchanged).toEqual(BODY);
    expect(unchanged).not.toBe(first);
    expect(keepSame(first.projects, unchanged.projects)).toBe(first.projects);
    const changed = await api<Bootstrap>("/api/bootstrap");
    expect(changed.jobs).toEqual([{ id: "j1" }]);
    expect(await api<Bootstrap>("/api/bootstrap")).toEqual(changed);
    expect(sent).toEqual([undefined, '"b1"', '"b1"', '"b2"']);
  });
});
