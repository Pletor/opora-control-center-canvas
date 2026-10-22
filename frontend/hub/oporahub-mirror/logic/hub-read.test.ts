import { describe, expect, it, vi } from "vitest";
import { hubRead, mirrorText } from "./hub-read";

describe("hub read", () => {
  it("parses a JSON body and rejects HTTP errors", async () => {
    const ok = vi.fn(async () => new Response(JSON.stringify({ a: 1 }), { status: 200 }));
    await expect(hubRead("/api/x?p=1", raw => raw as { a: number }, new AbortController().signal, ok)).resolves.toEqual({ a: 1 });
    const bad = vi.fn(async () => new Response("{}", { status: 503 }));
    await expect(hubRead("/api/x?p=1", raw => raw, new AbortController().signal, bad)).rejects.toThrow("/api/x není dostupné (HTTP 503).");
  });
  it("escapes < so the mirror cannot close its script tag", () => {
    expect(mirrorText({ s: "</script>" })).not.toContain("<");
    expect(JSON.parse(mirrorText({ s: "</script>" }))).toEqual({ s: "</script>" });
  });
});
