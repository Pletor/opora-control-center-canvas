// Co ukáže panel detailu Studia (docs/studio.md §3, ve Skutečnosti jen čtení): název, účel, stav, souhrn, vazby
// úrovně, díry mapy (karty i pod ní), cesty s odznakem ověření a odkaz do Architektury projektu. Čistá logika bez Reactu.
import { verificationBadge, verificationTitle, type VerificationBadge } from "@/project/architecture-editor/domain-site/logic/journey-verification";
import type { StudioLink } from "../../logic/studio-level";
import type { StudioFacts, StudioStatus } from "../../logic/studio-status";
import { studioDescendants, type StudioItem, type StudioTree } from "../../logic/studio-tree";
import { editorLabel, editorParams } from "../../logic/studio-route";
import { FLOW_LABEL } from "../../studio-canvas/logic/canvas-flow";
import { cardSubtitle, KIND_LABEL, STATE_LABEL, summaryLine } from "../../studio-card/logic/card-view";

export type DetailLink = { id: string; from: string; to: string; count: number; carries: StudioLink["carries"]; flow: string };
export type DetailHole = { place: string; message: string };
export type DetailJourney = { id: string; name: string; badge: VerificationBadge | null; title: string };
export type StudioDetailView = {
  id: string; name: string; kindLabel: string; subtitle: string; purpose: string;
  state: StudioStatus["state"]; stateLabel: string; summary: string;
  links: DetailLink[]; holes: DetailHole[]; journeys: DetailJourney[];
  editor: { label: string; params: Record<string, string> } | null;
};

/** Vazby, kterých se položka týká; otevřená úroveň (`focus`) ukáže všechny vazby mezi svými kartami. */
export function detailLinks(tree: StudioTree, links: StudioLink[], id: string, focus: boolean): DetailLink[] {
  const name = (key: string) => tree.items.get(key)?.name ?? key;
  return links.filter((link) => focus || link.source === id || link.target === id)
    .map((link) => ({ id: link.id, from: name(link.source), to: name(link.target), count: link.count, carries: link.carries, flow: FLOW_LABEL[link.carries] }));
}

/** Díry položky a všech jejích potomků v pořadí stromu, každá se jménem místa. */
export function detailHoles(tree: StudioTree, item: StudioItem, facts: StudioFacts): DetailHole[] {
  return [item, ...studioDescendants(tree, item.id)].filter((entry) => entry.node)
    .flatMap((entry) => (facts.holes.get(entry.id) ?? []).map((message) => ({ place: entry.name, message })));
}

export function detailView(input: { tree: StudioTree; item: StudioItem; status: StudioStatus; facts: StudioFacts; links: StudioLink[]; focus: boolean; project: string; workspace: string }): StudioDetailView {
  const { tree, item, status, facts, links, focus, project, workspace } = input;
  const params = editorParams(item, project, workspace);
  return {
    id: item.id, name: item.name, kindLabel: KIND_LABEL[item.kind], subtitle: cardSubtitle(item), purpose: item.purpose,
    state: status.state, stateLabel: STATE_LABEL[status.state], summary: summaryLine(status.summary),
    links: detailLinks(tree, links, item.id, focus), holes: detailHoles(tree, item, facts),
    journeys: status.journeys.map((journey) => {
      const badge = verificationBadge(journey.derived);
      return { id: journey.id, name: journey.name, badge, title: badge ? verificationTitle(badge) : "Odvození cesty zatím není načtené." };
    }),
    editor: params ? { label: editorLabel(item), params } : null,
  };
}
