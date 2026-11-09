import { Children, isValidElement, type ReactElement } from "react";
import { expect, it, vi } from "vitest";
import type { OverviewModels } from "@/hub/oporahub-overview/logic/models";
import type { GraphProposalsView } from "@/hub/graph-proposals/logic/use-graph-proposals";
import GraphProposalDetails from "@/hub/graph-proposals/components/GraphProposalDetails";
import DetailContent from "./DetailContent";

it.each([true, false])("routes graph inspection through parent drawer navigation (focused=%s)", focused => {
  const originalInspect = vi.fn(), open = vi.fn();
  const models = { graphProposals: { inspected: { id: "old" }, inspect: originalInspect },
    executions: { project: "p", workspace: "w" } } as unknown as OverviewModels;
  const rendered = DetailContent({ models, detail: { kind: "graph", id: focused ? "old" : undefined, title: "History" },
    open, currentAcceptedHead: null }) as ReactElement<{ model: GraphProposalsView; children?: ReactElement[] }>;
  const child = focused ? Children.toArray(rendered.props.children).find(element => isValidElement(element) && element.type === GraphProposalDetails) : rendered;
  (child as ReactElement<{ model: GraphProposalsView }>).props.model.inspect("latest");
  expect(open).toHaveBeenCalledExactlyOnceWith({ kind: "graph", id: "latest", title: "Uložený návrh plánu" });
  // The parent open operation also updates ohGraph and drawer identity before selecting the hook.
  expect(originalInspect).not.toHaveBeenCalled();
});
