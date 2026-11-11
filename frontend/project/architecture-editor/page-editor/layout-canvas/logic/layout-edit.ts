// Úpravy layoutu stránky (vrstva 1 plátna 2): přidat, posunout / vnořit, změnit velikost, přejmenovat a odebrat box.
// Každá úprava vrací celý nový seznam sekcí usazený přes `settleLayout` (upravený box zůstane, kolidující sourozenci
// uhnou dolů, předci povyrostou); ukládá rodič (`ArchitectureEditor`). Bez Reactu, test vedle.
import type { PageSection, PageSectionRole, SectionBox } from "@/shared/types/logic/types";
import { MAX_PAGE_SECTIONS } from "../../../domain-site/logic/page-site";
import { canNest, childrenOf, clampBox, COLUMNS, endBox, subtreeIds, type LayoutSection, type Point } from "./layout-grid";
import { settleLayout } from "./settle-layout";

/** Druh boxu z palety: role sekce, výchozí název a velikost. */
export type BoxKind = { role: PageSectionRole; name: string; w: number; h: number };

/** Volné id `sekce-N` (stejné schéma jako `addSection`). */
export function newSectionId(sections: Pick<PageSection, "id">[]): string {
  const used = new Set(sections.map((section) => section.id));
  let n = 1;
  while (used.has("sekce-" + n)) n += 1;
  return "sekce-" + n;
}

/** Nový box do rodiče: puštěný na buňku `at` tam zůstane a sourozenci pod ním uhnou dolů, jinak jde na konec.
 * Na limitu sekcí nebo v hloubce 3 nic. */
export function addBox(sections: LayoutSection[], kind: BoxKind, parent: string | null, at?: Point): LayoutSection[] {
  if (sections.length >= MAX_PAGE_SECTIONS || !canNest(sections, null, parent)) return sections;
  const box = at ? clampBox({ ...at, w: kind.w, h: kind.h }) : endBox(childrenOf(sections, parent).map((section) => section.box), kind.w, kind.h);
  const id = newSectionId(sections);
  return settleLayout([...sections, { id, role: kind.role, name: kind.name, intent: "", box, ...(parent ? { parent } : {}) }], id);
}

/** Posun nebo vnoření: box dostane rodiče a polohu, kolidující sourozenci uhnou dolů a předci povyrostou. */
export function moveBox(sections: LayoutSection[], id: string, parent: string | null, box: SectionBox): LayoutSection[] {
  if (!canNest(sections, id, parent)) return sections;
  const next = sections.map((section) => {
    if (section.id !== id) return section;
    const { parent: _old, ...rest } = section;
    return { ...rest, box: clampBox(box), ...(parent ? { parent } : {}) };
  });
  return settleLayout(next, id);
}

/** Nová velikost úchytem vpravo dole; poloha zůstává, sourozenci pod boxem uhnou a předci povyrostou. */
export function resizeBox(sections: LayoutSection[], id: string, w: number, h: number): LayoutSection[] {
  const next = sections.map((section) => (section.id === id ? { ...section, box: clampBox({ ...section.box, w: Math.min(w, COLUMNS - section.box.x), h }) } : section));
  return settleLayout(next, id);
}

/** Odebrání ✕: box i s vnořenými boxy (prvky logiky v nich přejdou na celou stránku u rodiče při uložení). */
export function removeBox(sections: LayoutSection[], id: string): LayoutSection[] {
  const gone = subtreeIds(sections, id);
  return sections.filter((section) => !gone.has(section.id));
}
