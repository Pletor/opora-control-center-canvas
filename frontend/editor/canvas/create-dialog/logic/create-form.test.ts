import { describe, expect, it } from "vitest";
import {
  buildCreated,
  canCreate,
  changeTargetSector,
  chooseOrigin,
  createRules,
  emptyCreateForm,
  missingFields,
  showsPurpose,
  specSummary,
  type CreateContext,
  type CreateForm,
} from "./create-form";

const existingSector = { id: "s1", sourceRef: { origin: "existing" as const, path: "frontend", kind: "directory" as const } };
const plannedSector = { id: "s2", sourceRef: { origin: "planned" as const, path: "", kind: "directory" as const } };
const bareSector = { id: "s3", sourceRef: null };
const ctx = (patch: Partial<CreateContext> = {}): CreateContext => ({ ancestorSector: null, targetSector: null, legacyFree: false, ...patch });
const form = (kind: "sector" | "node", patch: Partial<CreateForm> = {}): CreateForm => ({ ...emptyCreateForm(kind), name: "Karta", ...patch });

/** Kontrola, že výpis chybějícího je přesně opačná strana tlačítka „Vytvořit“. */
const consistent = (f: CreateForm, c: CreateContext) => expect(missingFields(f, c).length === 0).toBe(canCreate(f, c));

describe("pravidla platnosti", () => {
  it("bez názvu nejde vytvořit a výpis to řekne podle druhu", () => {
    const sector = { ...form("sector", { origin: "concept", purpose: "něco" }), name: " " };
    expect(missingFields(sector, ctx())).toEqual(["Název sektoru"]);
    expect(missingFields({ ...form("node", { origin: "concept", purpose: "x" }), name: "" }, ctx())).toEqual(["Název uzlu"]);
  });

  it("uzel v připojeném projektu vyžaduje cílový sektor (requiresTargetSector)", () => {
    const f = form("node", { origin: "planned", purpose: "něco" });
    expect(createRules(f, ctx()).requiresTargetSector).toBe(true);
    expect(missingFields(f, ctx())).toContain("Cílový sektor");
    consistent(f, ctx());
    expect(canCreate(f, ctx({ targetSector: existingSector }))).toBe(true);
    expect(canCreate(f, ctx({ targetSector: bareSector }))).toBe(true);
  });

  it("koncept uzlu cílový sektor nevyžaduje, ale chce popis", () => {
    const f = form("node", { origin: "concept" });
    expect(createRules(f, ctx()).requiresTargetSector).toBe(false);
    expect(missingFields(f, ctx())).toEqual(["Popis (co má tato část umět)"]);
    expect(canCreate({ ...f, purpose: "Umí přihlásit" }, ctx())).toBe(true);
  });

  it("legacyFree: volný uzel ani sektor nemají volbu zdroje", () => {
    const node = form("node");
    const sector = form("sector");
    expect(createRules(node, ctx({ legacyFree: true })).requiresModeChoice).toBe(false);
    expect(canCreate(node, ctx({ legacyFree: true }))).toBe(true);
    expect(canCreate(sector, ctx({ legacyFree: true }))).toBe(true);
    // Uzel v legacy projektu, jehož sektor má zdroj, volbu dostane.
    expect(createRules(node, ctx({ legacyFree: true, targetSector: existingSector })).requiresModeChoice).toBe(true);
  });

  it("mimo legacy projekt je původ zdroje povinný", () => {
    const f = form("sector");
    expect(missingFields(f, ctx())).toEqual(["Původ"]);
    consistent(f, ctx());
  });

  it("návrh sektoru chce nejméně 12 znaků podstaty", () => {
    const f = form("sector", { origin: "planned", purpose: "krátké" });
    expect(missingFields(f, ctx())).toEqual(["Popis návrhu sektoru (nejméně 12 znaků)"]);
    expect(canCreate({ ...f, purpose: "dost dlouhý text" }, ctx())).toBe(true);
  });

  it("návrh uzlu chce neprázdnou podstatu", () => {
    const f = form("node", { origin: "planned" });
    expect(missingFields(f, ctx({ targetSector: existingSector }))).toEqual(["Popis návrhu uzlu"]);
  });

  it("existující zdroj u uzlu jen v sektoru s existujícím zdrojem", () => {
    const f = form("node", { origin: "existing", path: "frontend/x" });
    expect(createRules(f, ctx({ targetSector: plannedSector })).existingAllowed).toBe(false);
    expect(missingFields(f, ctx({ targetSector: plannedSector }))).toEqual(["Sektor s napojeným existujícím zdrojem"]);
    expect(canCreate(f, ctx({ targetSector: existingSector }))).toBe(true);
    expect(missingFields({ ...f, path: null }, ctx({ targetSector: existingSector }))).toEqual(["Vybraný zdroj ve stromu"]);
    // Sektor existující zdroj smí vždy.
    expect(createRules(form("sector", { origin: "existing" }), ctx()).existingAllowed).toBe(true);
  });

  it("zamýšlená cesta uzlu potřebuje sektor, který ji ukotví", () => {
    const f = form("node", { origin: "planned", purpose: "x", plannedPath: "a/b" });
    expect(createRules(f, ctx({ targetSector: bareSector })).plannedPathReady).toBe(true);
    expect(missingFields(f, ctx({ targetSector: bareSector }))).toEqual([]);
    const result = buildCreated(f, ctx({ targetSector: bareSector }), { parent: null, nodes: [], id: "new" });
    expect(result.node.sourceRef?.path).toBe("a/b");
    expect(canCreate(f, ctx({ targetSector: existingSector }))).toBe(true);
  });

  it("výpis chybějícího a tlačítko se vždy shodnou", () => {
    const origins = [null, "existing", "planned", "concept"] as const;
    const sectors = [null, existingSector, plannedSector, bareSector];
    for (const kind of ["sector", "node"] as const)
      for (const origin of origins)
        for (const sector of sectors)
          for (const legacyFree of [false, true])
            for (const purpose of ["", "krátké", "dostatečně dlouhé"])
              for (const path of [null, "x"])
                for (const name of ["", "N"])
                  consistent(form(kind, { origin, purpose, path, name, plannedPath: "p" }), ctx({ targetSector: sector, legacyFree }));
  });
});

describe("změna cílového sektoru", () => {
  it("legacy volný uzel bez zdroje zahodí skrytý návrh, popis nechá", () => {
    const f = form("node", { origin: "planned", plannedPath: "a", purpose: "popis", entryKind: "file" });
    expect(changeTargetSector(f, bareSector, true)).toEqual({ ...f, targetSector: "s3", origin: null, path: null, entryKind: "directory", plannedPath: "" });
  });

  it("existující cestu je nutné vybrat znovu", () => {
    const f = form("node", { origin: "existing", path: "frontend/a" });
    expect(changeTargetSector(f, existingSector, false)).toMatchObject({ targetSector: "s1", origin: null, path: null });
  });

  it("relativní zamýšlená cesta se zahodí, když ji nový sektor nemá kam ukotvit", () => {
    const f = form("node", { origin: "planned", plannedPath: "a" });
    expect(changeTargetSector(f, bareSector, false).plannedPath).toBe("a");
    expect(changeTargetSector(f, null, false).plannedPath).toBe("");
    expect(changeTargetSector(f, existingSector, false).plannedPath).toBe("a");
  });

  it("volba původu zahodí vybranou cestu", () => {
    expect(chooseOrigin(form("node", { path: "x" }), "planned")).toMatchObject({ origin: "planned", path: null });
  });
});

describe("výsledek dialogu", () => {
  const scope = { parent: "layer", nodes: [{ parentId: "s1" }, { parentId: "s1" }, { parentId: "s1" }, { parentId: "layer" }], id: "new" };

  it("uzel jde do cílového sektoru s prefixovanou cestou a kartou bez prázdných klíčů", () => {
    const f = form("node", {
      origin: "planned", plannedPath: "login", purpose: " Přihlášení ", entryKind: "file",
      card: { layer: "frontend", status: "ready", due: "", model: "", effort: "high" },
    });
    const { node, spec } = buildCreated(f, ctx({ targetSector: existingSector }), scope);
    expect(spec).toBeNull();
    expect(node).toEqual({
      id: "new", parentId: "s1", kind: "node", name: "Karta", purpose: "Přihlášení", x: 0, y: 210,
      sourceRef: { origin: "planned", path: "frontend/login", kind: "file" },
      card: { layer: "frontend", status: "ready", effort: "high" },
    });
  });

  it("popis se ukládá vždy, i u existujícího zdroje; prázdná karta se nedává", () => {
    const f = form("node", { origin: "existing", path: "frontend/a", purpose: "Proč", entryKind: "file" });
    const { node } = buildCreated(f, ctx({ ancestorSector: existingSector }), scope);
    expect(node.parentId).toBe("layer");
    expect(node.purpose).toBe("Proč");
    expect(node.sourceRef).toEqual({ origin: "existing", path: "frontend/a", kind: "file" });
    expect("card" in node).toBe(false);
  });

  it("legacy volný uzel nemá sourceRef; sektor nese zadání, ne kartu", () => {
    expect("sourceRef" in buildCreated(form("node"), ctx({ legacyFree: true }), scope).node).toBe(false);
    const sector = form("sector", {
      origin: "existing", path: "", card: { layer: "backend", status: "ready", due: "", model: "", effort: "" },
      spec: { goal: " Cíl ", non_goals: "", acceptance: "" },
    });
    const result = buildCreated(sector, ctx(), scope);
    expect(result.node.sourceRef).toEqual({ origin: "existing", path: "", kind: "directory" });
    expect("card" in result.node).toBe(false);
    expect(result.spec).toEqual({ goal: "Cíl", non_goals: "", acceptance: "" });
    expect(buildCreated(form("sector", { origin: "concept" }), ctx(), scope).spec).toBeNull();
  });
});

describe("zobrazení dílků", () => {
  it("popis se ukáže, až je jasný původ, nebo hned, když projekt volbu původu nemá", () => {
    const f = form("node");
    expect(showsPurpose(f, createRules(f, ctx()))).toBe(false);
    const concept = chooseOrigin(f, "concept");
    expect(showsPurpose(concept, createRules(concept, ctx()))).toBe(true);
    expect(showsPurpose(f, createRules(f, ctx({ legacyFree: true })))).toBe(true);
  });

  it("souhrn zadání sektoru jmenuje jen vyplněná pole", () => {
    expect(specSummary({ goal: "", non_goals: " ", acceptance: "" })).toBe("");
    expect(specSummary({ goal: "Cíl", non_goals: "", acceptance: "Testy" })).toBe("cíl · hotovo když");
  });
});
