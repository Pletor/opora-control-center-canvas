import { createElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import type { Rule } from "@/shared/desktop-state/logic/types";
import RuleReview from "./RuleReview";

const proposal: Rule = { id: "p", text: "Návrh", kind: "must", scope: "project", target: "", by: "agent" };

/** Tlačítka z vráceného stromu (dílek nemá hooky, proto ho lze zavolat přímo bez DOM). */
function buttons(node: ReactNode): ReactElement<{ children: ReactNode; onClick: () => void }>[] {
  if (Array.isArray(node)) return node.flatMap(buttons);
  if (!isValidElement<{ children?: ReactNode }>(node)) return [];
  return node.type === "button" ? [node as ReactElement<{ children: ReactNode; onClick: () => void }>] : buttons(node.props.children);
}

it("shows approve and reject for an agent proposal of a project or path rule", () => {
  for (const rule of [proposal, { ...proposal, scope: "path" as const, target: "src" }]) {
    const html = renderToStaticMarkup(createElement(RuleReview, { rule, disabled: false, review: () => {} }));
    expect(html).toContain("✓ Schválit");
    expect(html).toContain("✗ Zamítnout");
    expect(html).toContain("návrh agenta – čeká na schválení");
  }
});

it("renders nothing for a human rule", () => {
  const { by: _by, ...human } = proposal;
  expect(renderToStaticMarkup(createElement(RuleReview, { rule: human, disabled: false, review: () => {} }))).toBe("");
});

it("clicking approve or reject sends the decision for the read proposal", () => {
  const review = vi.fn();
  const [approve, reject] = buttons(RuleReview({ rule: proposal, disabled: false, review }));
  expect(approve.props.children).toBe("✓ Schválit");
  approve.props.onClick();
  reject.props.onClick();
  expect(review.mock.calls).toEqual([[proposal, "approve"], [proposal, "reject"]]);
});
