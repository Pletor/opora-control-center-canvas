import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import ContentChanges from "./ContentChanges";
import { contentDetail, contentList, contentProposal } from "../logic/content-fixtures";
import type { ContentChangesView } from "../logic/use-content-changes";

function model(patch: Partial<ContentChangesView> = {}): ContentChangesView {
  return { project: "project", workspace: "work", list: contentList(), items: contentList().items,
    detail: contentDetail(), selectedId: contentProposal().id, busy: false, error: "", detailBusy: false, detailError: "", disabled: false,
    pending: false, notice: "", actionError: "", conflicts: [], acknowledged: false,
    refresh: vi.fn(), select: vi.fn(), cancel: vi.fn(), acknowledge: vi.fn(), accept: vi.fn(), rebase: vi.fn(), ...patch };
}
describe("visible content review", () => {
  it("shows all three values, original ownership and full baseline consent without executing markup", () => {
    const html = renderToStaticMarkup(createElement(ContentChanges, { model: model(), currentAcceptedHead: contentList().acceptedHead }));
    for (const text of ["Přijatý obsah", "Pozorovaný pracovní stav", "Navržená hodnota", "Working", "Desired", "zdrojová revize 1", "kolo 2", "celý výchozí obsah", contentProposal().baseContentDigest]) expect(html).toContain(text);
    expect(html).not.toContain("<script>");
    expect(html).toContain("může zneplatnit běžící úlohy");
    expect(html).toMatch(/disabled="">Přijmout přesný návrh/);
  });
  it("enables acceptance only after exact consent and fresh common head", () => {
    const ready = renderToStaticMarkup(createElement(ContentChanges, { model: model({ acknowledged: true }), currentAcceptedHead: contentList().acceptedHead }));
    expect(ready).not.toMatch(/disabled="">Přijmout přesný návrh/);
    const stale = renderToStaticMarkup(createElement(ContentChanges, { model: model({ acknowledged: true }), currentAcceptedHead: "e".repeat(40) }));
    expect(stale).toMatch(/disabled="">Přijmout přesný návrh/);
  });
  it("never substitutes another detail for a missing exact ID and marks absent model unavailable", () => {
    const missing = renderToStaticMarkup(createElement(ContentChanges, { model: model(), requestedId: "e".repeat(40), currentAcceptedHead: contentList().acceptedHead }));
    expect(missing).toContain("Nebyl nahrazen jiným návrhem");
    expect(missing).not.toContain("Navržená hodnota");
    expect(renderToStaticMarkup(createElement(ContentChanges, { currentAcceptedHead: null }))).toContain("nejsou dostupné");
  });
});
