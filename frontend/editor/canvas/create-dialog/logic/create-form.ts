// Čistý model pop-upu tvorby sektoru a uzlu (docs/kontext-karet-a-index.md §7). Bez Reactu: formulář
// je obyčejný objekt, pravidla platnosti jsou funkce nad ním a nad hotovým kontextem od rodiče
// (sektor vrstvy, vybraný cílový sektor, schopnost projektu `legacyFree`). Pravidla jsou přenesena
// z App.tsx beze změny; nové je jen `missingFields` (co chybí u neaktivního „Vytvořit“), karta uzlu
// a zadání sektoru.
import type { CanvasNode, SpecFields } from "@/shared/types/logic/types";
import { normalizeCard } from "@/shared/card-context/logic/card-context";
import { emptyCard, type CardDraft } from "@/editor/canvas/create-dialog/logic/card-draft";

export type CreateKind = "sector" | "node";
export type CreateOrigin = "existing" | "planned" | "concept" | null;
/** Druh vybraného nebo navrhovaného zdroje (složka / soubor); se zdrojem projektu nemá nic společného. */
export type EntryKind = "directory" | "file";

export type CreateForm = {
  kind: CreateKind;
  name: string;
  origin: CreateOrigin;
  /** Vybraný existující zdroj; `null` = ve stromu zatím nic nevybráno. */
  path: string | null;
  entryKind: EntryKind;
  plannedPath: string;
  purpose: string;
  targetSector: string;
  card: CardDraft;
  spec: SpecFields;
};

type SectorRef = Pick<CanvasNode, "id" | "sourceRef">;

/** Hotová data od rodiče: sektor, ve kterém vrstva leží, vybraný cílový sektor a schopnost projektu. */
export type CreateContext = {
  ancestorSector: SectorRef | null;
  targetSector: SectorRef | null;
  /** Historický vestavěný draft smí mít volné uzly a sektory bez volby zdroje (`project-capabilities`). */
  legacyFree: boolean;
};

export const MIN_SECTOR_PURPOSE = 12;
export const emptySpec = (): SpecFields => ({ goal: "", non_goals: "", acceptance: "" });

export const emptyCreateForm = (kind: CreateKind): CreateForm => ({
  kind,
  name: "",
  origin: null,
  path: null,
  entryKind: "directory",
  plannedPath: "",
  purpose: "",
  targetSector: "",
  card: emptyCard(),
  spec: emptySpec(),
});

export type CreateRules = {
  effectiveSector: SectorRef | null;
  concept: boolean;
  requiresTargetSector: boolean;
  requiresModeChoice: boolean;
  existingAllowed: boolean;
  purposeReady: boolean;
  pathReady: boolean;
  plannedPathReady: boolean;
  /** Všechna pravidla kromě názvu; název hlídá `canCreate`. */
  ready: boolean;
};

export function createRules(form: CreateForm, ctx: CreateContext): CreateRules {
  const node = form.kind === "node";
  const effectiveSector = node ? (ctx.ancestorSector ?? ctx.targetSector) : null;
  const concept = form.origin === "concept";
  const legacyFreeSector = !node && ctx.legacyFree;
  const requiresTargetSector = node && !effectiveSector && !ctx.legacyFree && !concept;
  const requiresModeChoice = !legacyFreeSector && !(node && ctx.legacyFree && !effectiveSector?.sourceRef);
  const existingAllowed = !node || effectiveSector?.sourceRef?.origin === "existing";
  const purpose = form.purpose.trim();
  const purposeReady = concept
    ? purpose.length > 0
    : form.origin !== "planned" || (node ? purpose.length > 0 : purpose.length >= MIN_SECTOR_PURPOSE);
  const pathReady = form.origin !== "existing" || (existingAllowed && form.path !== null);
  const plannedPathReady =
    form.origin !== "planned" || !node || !form.plannedPath.trim() ||
    effectiveSector?.sourceRef?.origin === "existing" || !!effectiveSector?.sourceRef?.path;
  const ready = !requiresTargetSector && plannedPathReady &&
    (!requiresModeChoice || (form.origin !== null && purposeReady && pathReady));
  return { effectiveSector, concept, requiresTargetSector, requiresModeChoice, existingAllowed, purposeReady, pathReady, plannedPathReady, ready };
}

export const nameLabel = (kind: CreateKind): string => (kind === "sector" ? "Název sektoru" : "Název uzlu");

/** Co chybí, aby šlo vytvořit; prázdný seznam právě tehdy, když `canCreate` vrací true. */
export function missingFields(form: CreateForm, ctx: CreateContext): string[] {
  const rules = createRules(form, ctx);
  const missing: string[] = [];
  if (!form.name.trim()) missing.push(nameLabel(form.kind));
  if (rules.requiresTargetSector) missing.push("Cílový sektor");
  if (!rules.plannedPathReady) missing.push("Cílový sektor s cestou (zamýšlenou cestu není kam ukotvit)");
  if (rules.requiresModeChoice) {
    if (form.origin === null) missing.push("Původ");
    else {
      if (!rules.purposeReady)
        missing.push(
          rules.concept
            ? "Popis (co má tato část umět)"
            : form.kind === "sector"
              ? `Popis návrhu sektoru (nejméně ${MIN_SECTOR_PURPOSE} znaků)`
              : "Popis návrhu uzlu",
        );
      if (!rules.pathReady)
        missing.push(rules.existingAllowed ? "Vybraný zdroj ve stromu" : "Sektor s napojeným existujícím zdrojem");
    }
  }
  return missing;
}

export const canCreate = (form: CreateForm, ctx: CreateContext): boolean =>
  !!form.name.trim() && createRules(form, ctx).ready;

/**
 * Změna cílového sektoru. Legacy volný uzel bez zdroje volbu zdroje nemá: skrytý návrh se zahodí,
 * aby neblokoval vytvoření ani neprosákl do uzlu bez zdroje. Popis zůstává, protože je vidět vždy.
 * Jinak se rozepsaný návrh nemaže; jen existující cestu je nutné vybrat znovu v rozsahu nového
 * sektoru a relativní zamýšlená cesta se zahodí, když ji nový sektor nemá kam ukotvit.
 */
export function changeTargetSector(form: CreateForm, next: SectorRef | null, legacyFree: boolean): CreateForm {
  const targetSector = next?.id ?? "";
  if (legacyFree && !next?.sourceRef)
    return { ...form, targetSector, origin: null, path: null, entryKind: "directory", plannedPath: "" };
  if (form.origin === "existing") return { ...form, targetSector, origin: null, path: null };
  if (form.origin === "planned" && form.plannedPath.trim() && next?.sourceRef?.origin !== "existing" && !next?.sourceRef?.path)
    return { ...form, targetSector, plannedPath: "" };
  return { ...form, targetSector };
}

/** Popis je vidět, jakmile je jasný původ; projekt bez volby původu ho ukáže hned (nepovinný). */
export const showsPurpose = (form: CreateForm, rules: CreateRules): boolean => !rules.requiresModeChoice || form.origin !== null;

/** Souhrn sbalené sekce „Zadání sektoru“: která z polí jsou vyplněná, např. `cíl · hotovo když`. */
export function specSummary(spec: SpecFields): string {
  const names: [keyof SpecFields, string][] = [["goal", "cíl"], ["non_goals", "co nedělat"], ["acceptance", "hotovo když"]];
  return names.filter(([key]) => spec[key].trim()).map(([, name]) => name).join(" · ");
}

/** Přepnutí původu zdroje vždy zahodí vybranou cestu ve stromu. */
export const chooseOrigin = (form: CreateForm, origin: Exclude<CreateOrigin, null>): CreateForm => ({ ...form, origin, path: null });

/** Hotový výsledek dialogu: nový uzel grafu a zadání sektoru (jen když je co uložit). */
export type CreateResult = { node: CanvasNode; spec: SpecFields | null };

/**
 * Uzel z vyplněného formuláře. Uzel bez sektoru ve vrstvě jde do vybraného cílového sektoru, jinak
 * do aktuální vrstvy. Zamýšlená cesta uzlu se prefixuje cestou sektoru. Popis (`purpose`) se ukládá
 * vždy; prázdná karta se do uzlu nedává; sektor kartu nemá, zato nese zadání (cíl, hranice, hotovo).
 */
export function buildCreated(
  form: CreateForm,
  ctx: CreateContext,
  scope: { parent: string | null; nodes: Pick<CanvasNode, "parentId">[]; id: string },
): CreateResult {
  const rules = createRules(form, ctx);
  const sector = rules.effectiveSector;
  const parentId = form.kind === "node" && !ctx.ancestorSector && ctx.targetSector ? ctx.targetSector.id : scope.parent;
  const siblings = scope.nodes.filter((n) => n.parentId === parentId).length;
  const planned = form.plannedPath.trim();
  const plannedNodePath = form.kind === "node" && sector?.sourceRef?.path && planned ? `${sector.sourceRef.path}/${planned}` : planned;
  let sourceRef: CanvasNode["sourceRef"] = null;
  if (form.kind === "sector" && form.origin === "existing") sourceRef = { origin: "existing", path: form.path ?? "", kind: "directory" };
  else if (form.kind === "sector" && form.origin === "planned") sourceRef = { origin: "planned", path: planned, kind: "directory" };
  else if (form.kind === "node" && sector && form.origin === "existing") sourceRef = { origin: "existing", path: form.path ?? "", kind: form.entryKind };
  else if (form.kind === "node" && sector && form.origin === "planned") sourceRef = { origin: "planned", path: plannedNodePath, kind: form.entryKind };
  const card = form.kind === "node" ? normalizeCard(form.card) : undefined;
  const node: CanvasNode = {
    id: scope.id,
    parentId,
    kind: form.kind,
    name: form.name,
    purpose: form.purpose.trim(),
    x: (siblings % 3) * 310,
    y: Math.floor(siblings / 3) * 210,
    ...(sourceRef ? { sourceRef } : {}),
    ...(card ? { card } : {}),
  };
  const spec = form.kind === "sector" ? trimSpec(form.spec) : null;
  return { node, spec };
}

function trimSpec(spec: SpecFields): SpecFields | null {
  const next = { goal: spec.goal.trim(), non_goals: spec.non_goals.trim(), acceptance: spec.acceptance.trim() };
  return next.goal || next.non_goals || next.acceptance ? next : null;
}
