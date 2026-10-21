import { Children, createElement, isValidElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import { ProcessSyncView } from "./ProcessSync";
import { processFixture } from "../logic/process-fixtures";
vi.mock("@/shared/hooks/logic/use-copy-text", () => ({ useCopyText: () => ({ status: "idle", copy: vi.fn(), fieldRef: { current: null } }) }));

it("renders scoped process states, observation and copyable API without implied verification", () => {
  const snapshot = processFixture(); snapshot.items[0].status = "reported";
  const html = renderToStaticMarkup(createElement(ProcessSyncView, { snapshot, busy: false, error: "", refresh: vi.fn(), project: "draft", workspace: "draft", open: vi.fn(), onImprove: vi.fn() }));
  for (const text of ["Proces Control Center", "Kontrola změny", "Nahlášeno · vyžaduje kontrolu", "Navrhnout zlepšení", "Poslední pozorování", "GET /api/oporahub/process?project=draft", "Nahlášení není ověření, merge ani nasazení."]) expect(html).toContain(text);
  expect(html).not.toContain("<script");
});
it("an unavailable process shows the error and no old ready cards", () => {
  const html = renderToStaticMarkup(createElement(ProcessSyncView, { snapshot: null, busy: false, error: "Zdroj nedostupný", refresh: vi.fn(), project: "other", workspace: "draft", open: vi.fn(), onImprove: vi.fn() }));
  expect(html).toContain("Zdroj nedostupný"); expect(html).not.toContain("Připraveno k převzetí"); expect(html).toContain("project=other");
});
it("refresh/error keeps exact opener actions mounted and focusable but their handlers cannot navigate or propose", () => {
  const snapshot = processFixture(), open = vi.fn(), onImprove = vi.fn();
  function findButton(tree: ReactNode, label: string): { onClick: () => void; disabled?: boolean; "aria-disabled"?: boolean } | undefined {
    if (!isValidElement<{ children?: ReactNode; onClick: () => void; disabled?: boolean; "aria-disabled"?: boolean }>(tree)) return;
    if (tree.type === "button" && tree.props.children === label) return tree.props;
    for (const child of Children.toArray(tree.props.children)) { const found = findButton(child, label); if (found) return found; }
  }
  for (const state of [{ busy: true, error: "" }, { busy: false, error: "Unavailable" }]) {
    const props = { ...state, snapshot, refresh: vi.fn(), project: "draft", workspace: "draft", open, onImprove };
    const tree = ProcessSyncView(props);
    const action = findButton(tree, "Otevřít další krok")!, improvement = findButton(tree, "Navrhnout zlepšení")!;
    expect(action["aria-disabled"]).toBe(true); expect(action.disabled).toBeUndefined();
    action.onClick(); improvement.onClick(); expect(open).not.toHaveBeenCalled(); expect(onImprove).not.toHaveBeenCalled();
    const html = renderToStaticMarkup(createElement(ProcessSyncView, props));
    expect(html).toContain("Kontrola změny"); expect(html).toContain(state.busy ? "Obnovuji" : "Historické pozorování");
  }
  const tree = ProcessSyncView({ snapshot, busy: false, error: "", refresh: vi.fn(), project: "draft", workspace: "draft", open, onImprove });
  findButton(tree, "Navrhnout zlepšení")!.onClick(); expect(onImprove).toHaveBeenCalledExactlyOnceWith("task-1", "Kontrola změny");
});
