import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import FormalDetail from "./FormalDetail";
import FormalVerification from "./FormalVerification";
import type { FormalVerificationView } from "../logic/use-formal-verification";
import { formalFixture } from "../logic/formal-verification-fixtures";

describe("formal evidence view boundaries", () => {
  it("keeps passed explicitly unverified and displays exact plan, claims, bounds and reported commit", () => {
    const record = formalFixture();
    const html = renderToStaticMarkup(createElement(FormalDetail, { record, currentAcceptedHead: record.acceptedRevision }));
    for (const value of ["Nahlášeno: prošlo", "nezávislé ověření nedoloženo", "nepoužitelné pro automatické rozhodnutí", record.acceptedRevision,
      record.verification.source.commitSha, record.verification.claims[0].statement, "Finite state space", "workers", "Manifest vstupů"])
      expect(html).toContain(value);
    expect(html).not.toMatch(/class="[^"]*(success|verified)/);
    expect(html).toContain('download=""');
  });
  it("escapes imported strings and never previews artifact bytes as executable HTML", () => {
    const record = formalFixture();
    record.verification.claims[0].statement = '<img src=x onerror="alert(1)">';
    record.verification.configuration = { bounds: '<script>alert("x")</script>' };
    record.report!.summary = "<svg onload=alert(1)>";
    const html = renderToStaticMarkup(createElement(FormalDetail, { record, currentAcceptedHead: null }));
    expect(html).toContain("&lt;img");
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<svg");
    expect(html).not.toContain("Historický podklad");
  });
  it("does not offer a missing/corrupt blob as a download", () => {
    const record = formalFixture();
    record.verification.artifacts[0].available = false;
    record.report!.artifacts = [];
    const html = renderToStaticMarkup(createElement(FormalDetail, { record, currentAcceptedHead: "9".repeat(40) }));
    expect(html).toContain("chybí nebo je poškozený");
    expect(html).not.toContain("/artifacts/");
    expect(html).toContain("Historický podklad");
  });
  it("keeps empty, loading and missing selection states explicit without another record fallback", () => {
    const record = formalFixture();
    const model = { requests: [], busy: false, error: "", selectedId: "", selected: null, detailBusy: false, detailError: "", missingSelection: false,
      refresh: vi.fn(), select: vi.fn() } as unknown as FormalVerificationView;
    expect(renderToStaticMarkup(createElement(FormalVerification, { model, currentAcceptedHead: null }))).toContain("zatím nejsou formální požadavky");
    const busy = renderToStaticMarkup(createElement(FormalVerification, { model: { ...model, busy: true }, currentAcceptedHead: null }));
    expect(busy).toContain("Načítám historii");
    const missing = renderToStaticMarkup(createElement(FormalVerification, { model: { ...model, selectedId: "f".repeat(32), selected: record, requests: [record], detailError: "missing" }, currentAcceptedHead: null }));
    expect(missing).toContain("Nebyl nahrazen jiným požadavkem");
    expect(missing).not.toContain(record.verification.claims[0].statement);
    expect(missing).not.toContain("Přesný formální podklad");
  });
});
