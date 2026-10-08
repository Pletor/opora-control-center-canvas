import { afterEach, expect, it, vi } from "vitest";
import { api } from "./types";

afterEach(() => vi.unstubAllGlobals());
it("shares one in-flight GET, then permits a fresh read", async () => {
  let done!: (response: Response) => void;
  const fetch = vi.fn(() => new Promise<Response>(resolve => { done = resolve; }));
  vi.stubGlobal("fetch", fetch);
  const first = api<{revision:number}>("/api/dedup-test");
  const second = api<{revision:number}>("/api/dedup-test");
  expect(fetch).toHaveBeenCalledTimes(1);
  done(new Response('{"revision":1}'));
  expect(await first).toEqual(await second);
  (await first).revision = 99;
  expect((await second).revision).toBe(1);
  const third = api("/api/dedup-test");
  expect(fetch).toHaveBeenCalledTimes(2);
  done(new Response('{"revision":2}'));
  expect(await third).toEqual({revision:2});
});
