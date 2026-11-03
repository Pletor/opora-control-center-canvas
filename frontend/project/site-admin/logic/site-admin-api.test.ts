import { afterEach, expect, it, vi } from "vitest";
import { ApiError } from "@/shared/types/logic/types";
import { saveProblem, saveSiteAdmin, siteAdminUrls } from "./site-admin-api";
import type { SiteDocument } from "./site-document";

afterEach(() => vi.unstubAllGlobals());

it("builds the site admin addresses for one project", () => {
  expect(siteAdminUrls.document("p1")).toBe("/api/site-admin?project=p1");
  expect(siteAdminUrls.file("p1", "tokens.css")).toBe("/api/site-admin/tokens.css?project=p1");
  expect(siteAdminUrls.font("p1", "Inter Var.woff2")).toBe("/api/site-admin/fonts/Inter%20Var.woff2?project=p1");
  expect(siteAdminUrls.file("p1", "components.css")).toBe("/api/site-admin/components.css?project=p1");
  expect(siteAdminUrls.asset("p1", "pozadí", "a b.png")).toBe("/api/site-admin/assets/poz%C3%A1d%C3%AD/a%20b.png?project=p1");
});

it("reads a rejected custom CSS from the 422 detail and keeps other failures as text", () => {
  const detail = { message: "settings.customCss.button.primary, řádek 3: !important není povolené.", path: "settings.customCss.button.primary", line: 3, reason: "!important není povolené." };
  expect(saveProblem(new ApiError("Požadavek se nezdařil (HTTP 422).", 422, { detail }))).toEqual({ message: detail.message, invalid: detail });
  expect(saveProblem(new ApiError("x", 422, { detail: "settings.buttons: neznámé pole y." }))).toEqual({ message: "settings.buttons: neznámé pole y.", invalid: null });
  expect(saveProblem(new Error("síť"))).toEqual({ message: "síť", invalid: null });
});

it("saves with PUT over the expected revision and leaves revision and lastChange to the server", async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return { ok: true, status: 200, text: async () => JSON.stringify({ revision: 4, document: {}, notes: [] }), headers: { get: () => null } };
  });
  const document = { v: 1, title: "Ember", revision: 3, lastChange: { by: "x" }, settings: {}, design: {} } as unknown as SiteDocument;
  const saved = await saveSiteAdmin("p1", 3, document, "barvy");
  const write = calls.find((call) => call.init?.method === "PUT")!;
  expect(write.url).toBe("/api/site-admin?project=p1");
  expect(JSON.parse(String(write.init!.body))).toEqual({ expectedRevision: 3, note: "barvy", document: { v: 1, title: "Ember", settings: {}, design: {} } });
  expect(saved.revision).toBe(4);
});
