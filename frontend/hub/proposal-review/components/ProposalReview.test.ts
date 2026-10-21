import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ProposalReview from "./ProposalReview";
import AcceptancePolicy from "./AcceptancePolicy";
import { reviewModel, reviewContext, reviewEvent, reviewPolicy, reviewTarget } from "../logic/review-fixtures";

describe("visible risk and discussion", () => {
  it("shows explicit unavailable review without invented independent votes", () => {
    const html = renderToStaticMarkup(createElement(ProposalReview, { ...reviewTarget, acceptedHead: null }));
    expect(html).toContain("Splnění podmínek není doloženo");
    expect(html).not.toContain("neblokují přijetí");
    expect(renderToStaticMarkup(createElement(AcceptancePolicy, {}))).toContain("nejsou dostupná");
  });
  it("renders provenance, blocking reason and human resolution with inert anchored text", () => {
    const finding = reviewEvent(), policy = reviewPolicy();
    const context = reviewContext({ policy, policyHead: policy.id, events: [finding], reviewHead: finding.id, openFindings: [finding],
      acknowledgementRequired: true, canAcknowledge: true, canAccept: false, eligible: false, blockedReasons: ["Blocking finding open"] });
    const html = renderToStaticMarkup(createElement(ProposalReview, { ...reviewTarget, model: reviewModel({ context }), acceptedHead: context.acceptedHead }));
    for (const text of ["Kritické", "Blokující nález", "Tvrzení agenta", "Vypořádání nálezu", "Odůvodnění vypořádání", "Potvrdit přesné riziko", "Blocking finding open", "/changes/0/value"]) expect(html).toContain(text);
    expect(html).not.toContain("<script>");
    expect(html).toMatch(/disabled="">Potvrdit přesné riziko/);
  });
  it("known null accepted head for first graph is coherent and absence of receipt stays explicit", () => {
    const context = reviewContext({ proposalKind: "graph-addition", acceptedHead: null, parentAcceptedHead: null });
    const html = renderToStaticMarkup(createElement(ProposalReview, { proposalKind: "graph-addition", proposalId: context.proposalId, model: reviewModel({ context }), acceptedHead: null }));
    expect(html).toContain("Načtené podmínky review neblokují přijetí");
    expect(html).toContain("Absence dokladu neznamená provedené review");
  });
});
