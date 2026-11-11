// Zápisy převzetí skenu po částech (`adopt-scan.ts`) nad úložištěm editoru architektury. Volá je jen rodič
// `ArchitectureEditor` (jediný, kdo ukládá). Každý zápis grafu si nejdřív znovu načte pohled a píše nad jeho digestem,
// protože předchozí část graf mezitím změnila. Výřez boxu jde stejnou cestou jako ruční inspirace (`/api/drawing-file`),
// tokeny stejným zápisem jako Správa webu (`PUT /api/site-admin` s revizí; 409 = část selže, nic se nepřepíše),
// plátno logiky stejně jako dvojklik na prvek (`POST /api/library/project-flows`) a první verze jako ruční uložení draftu.
import type { Graph, PageSection, View } from "@/shared/types/logic/types";
import { uploadImage } from "@/editor/storyboard/logic/sketch-files";
import { createElementFlow, saveFlowDraft } from "@/project/library-canvas/logic/library-api";
import { loadSiteAdmin, saveSiteAdmin } from "@/project/site-admin/logic/site-admin-api";
import type { ArchitecturePlanResult } from "../../../logic/use-architecture-graph";
import { scanLogicPlan, setEditorNodeSection, setEditorPageLayout } from "../../../logic/editor-model";
import { adoptScanLayout, fetchCapture } from "./page-scan";
import { mergeDesignTokens } from "./scan-design";
import { withCaptureInspiration, type AdoptDeps } from "./adopt-scan";

type Store = {
  reload: () => Promise<View>;
  saveGraph: (graph: Graph, expectedDigest: string) => Promise<View>;
  applyPlan: (plan: object, expectedDigest: string) => Promise<ArchitecturePlanResult>;
};
type Context = {
  project: string; workspace: string; pageId: string; scanId: string; store: Store; contentLock: string | null;
  /** Zámek rozsahu editoru (struktura / obsah, uzavřené karty); vyhodí větu proč. */
  writable: (id: string, kind?: "content" | "structure") => void;
};

function pageSections(view: View, pageId: string): PageSection[] {
  const page = view.graph.nodes.find((node) => node.id === pageId);
  if (!page || page.site?.kind !== "page") throw new Error("Stránka již neexistuje.");
  return page.site.sections ?? [];
}

export function scanAdoptDeps(context: Context): AdoptDeps {
  const { project, workspace, pageId, scanId, store, writable } = context;
  const scope = { project, workspace };
  return {
    contentLock: context.contentLock,
    /** Prvky ztracených boxů na celou stránku (graf), pak layout přes `/api/page-plan` se `scanId` (server zapíše `source: "scan"`). */
    async saveLayout(sections) {
      writable(pageId, "structure");
      const view = await store.reload();
      const { touched } = setEditorPageLayout(view.graph, pageId, sections);
      if (touched.length) {
        touched.forEach((id) => writable(id));
        await store.saveGraph(touched.reduce((next, id) => setEditorNodeSection(next, id, null), view.graph), view.digest);
      }
      await adoptScanLayout(scope, pageId, sections, scanId);
    },
    async saveInspirations(files) {
      writable(pageId, "content");
      const view = await store.reload();
      const sections = pageSections(view, pageId);
      const hit = sections.filter((section) => files.has(section.id)).length;
      if (hit) await store.saveGraph(setEditorPageLayout(view.graph, pageId, withCaptureInspiration(sections, files)).graph, view.digest);
      return hit;
    },
    uploadCapture: async (name) => uploadImage(project, workspace, await fetchCapture(scope, scanId, name), "image/png"),
    async saveTokens(design) {
      const site = await loadSiteAdmin(project);
      const { tokens, changes } = mergeDesignTokens(site.document.design.tokens, design);
      if (!changes.length) return { changes: 0, notes: [] };
      const saved = await saveSiteAdmin(project, site.revision, { ...site.document, design: { ...site.document.design, tokens } }, "Design ze skenu webu");
      return { changes: changes.length, notes: saved.notes ?? [] };
    },
    /** Prvky jedním plánem nad čerstvým digestem; box, který na stránce není (layout se nepřevzal), = celá stránka. */
    async insertLogic(logic) {
      writable(pageId);
      const view = await store.reload();
      const ids = new Set(pageSections(view, pageId).map((section) => section.id));
      const result = await store.applyPlan(scanLogicPlan(pageId, logic.map((item) => ({ ...item, section: item.section && ids.has(item.section) ? item.section : null }))), view.digest);
      // `scanLogicPlan` dává prvkům ref `logic-<pořadí>`; server vrátí id uzlu ke každému refu.
      return logic.map((_, index) => result.refs[`logic-${index}`] ?? null);
    },
    async createFlow(nodeId, title, graph) {
      const flow = await createElementFlow(project, workspace, nodeId, title);
      if (flow.versions?.length) return false;
      await saveFlowDraft(flow.id, graph, null);
      return true;
    },
  };
}
