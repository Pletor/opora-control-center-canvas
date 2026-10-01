import { describe, expect, it } from "vitest";
import {
  MAX_MEMORY_TEXT,
  MEMORY_MAX_TOKENS,
  NEEDS_PROVISIONING_BANNER,
  NO_ROLE_LABEL,
  briefRoleMemory,
  canLend,
  canRecall,
  canRemember,
  formatScore,
  groupByOrigin,
  lendPayload,
  memoryItems,
  memoryModel,
  memoryQuery,
  missingRoleIds,
  missingRoleLabels,
  provisionPayload,
  provisionSummary,
  recallPayload,
  rememberPayload,
  roleLabel,
  roleOptions,
  type MemoryItem,
  type MemoryRole,
} from "./agent-memory";

const ROLES: MemoryRole[] = [
  { id: "role-frontend", label: "Frontend", description: "Obrazovky a dílky." },
  { id: "role-db", label: "Databáze", description: "Schéma a migrace." },
];

const item = (uri: string, origin: string, score = 0.5, body = "text"): MemoryItem => ({ uri, text: body, score, origin });
const SCOPE = { project: "p1", workspace: "main", nodeId: "n1" };

describe("agent-memory: položky a skóre", () => {
  it("položka bez adresy není položka paměti", () => {
    expect(memoryItems([{ text: "bez uri" }, { uri: "viking://a" }])).toEqual([
      { uri: "viking://a", text: "", score: 0, origin: "" },
    ]);
  });

  it("cizí tvar odpovědi skončí prázdným seznamem, ne výjimkou", () => {
    expect(memoryItems(null)).toEqual([]);
    expect(memoryItems("text")).toEqual([]);
    expect(memoryItems([1, "a", null])).toEqual([]);
  });

  it("skóre se pojmenuje a zaokrouhlí na dvě desetiny", () => {
    expect(formatScore(0.4567)).toBe("podobnost 0.46");
    expect(formatScore(1)).toBe("podobnost 1.00");
  });

  it("chybějící nebo nesmyslné skóre se nevydává za jistotu", () => {
    expect(formatScore(undefined)).toBe("podobnost 0.00");
    expect(formatScore(Number.NaN)).toBe("podobnost 0.00");
    expect(formatScore("0.9")).toBe("podobnost 0.00");
  });

  it("název role je z knihovny, neznámé id se ukáže tak, jak přišlo", () => {
    expect(roleLabel("role-db", ROLES)).toBe("Databáze");
    expect(roleLabel("role-nic", ROLES)).toBe("role-nic");
  });
});

describe("agent-memory: skupiny podle původu", () => {
  it("pořadí je vlastní zkušenost, tento projekt, teprve pak půjčky", () => {
    const groups = groupByOrigin(
      [item("c", "lent:role-db"), item("b", "project"), item("a", "self")],
      ROLES,
    );
    expect(groups.map((group) => group.label)).toEqual([
      "Vlastní zkušenost", "Tento projekt", "Zapůjčeno od Databáze",
    ]);
  });

  it("půjčka nikdy nesplyne s vlastní zkušeností, i když je od neznámé role", () => {
    const [group] = groupByOrigin([item("a", "lent:role-x")], ROLES);
    expect(group.label).toBe("Zapůjčeno od role-x");
    expect(group.origin).toBe("lent:role-x");
  });

  it("položky stejného původu drží pohromadě v pořadí, v jakém přišly", () => {
    const [group] = groupByOrigin([item("a", "self"), item("b", "self")]);
    expect(group.items.map((entry) => entry.uri)).toEqual(["a", "b"]);
  });

  it("chybějící původ dostane vlastní skupinu, nepřipíše se roli", () => {
    expect(groupByOrigin([item("a", "")])[0]).toMatchObject({ id: "unknown", label: "Neuvedený původ" });
  });

  it("bez položek nejsou žádné skupiny", () => {
    expect(groupByOrigin([])).toEqual([]);
  });
});

describe("agent-memory: pohled panelu", () => {
  it("dokud stav nedorazil, není to vypnuto, ale neznámo", () => {
    expect(memoryModel(null, null)).toMatchObject({ state: "unknown", groups: [], empty: true, role: null });
  });

  it("vypnutá paměť nese důvod ze serveru", () => {
    expect(memoryModel({ status: "disabled", reason: "Paměť rolí je v nastavení aplikace vypnutá." }, null))
      .toMatchObject({ state: "disabled", reason: "Paměť rolí je v nastavení aplikace vypnutá." });
  });

  it("nedostupný server se hlásí jako nedostupný, ne jako prázdná paměť", () => {
    const view = memoryModel({ status: "unavailable", reason: "OpenViking neodpověděl." }, null);
    expect(view.state).toBe("unavailable");
    expect(view.empty).toBe(true);
  });

  it("karta bez role přebíjí běžící stav: vybavení říká skipped", () => {
    const view = memoryModel(
      { status: "configured", reason: "OpenViking odpovídá na loopbacku." },
      { status: "skipped", reason: "Karta nemá přiřazenou roli agenta.", role: null, items: [] },
    );
    expect(view.state).toBe("skipped");
    expect(view.reason).toBe("Karta nemá přiřazenou roli agenta.");
  });

  it("vybavení složí skupiny, roli i ořez", () => {
    const view = memoryModel(
      { status: "configured" },
      { status: "configured", role: "role-frontend", truncated: true, items: [item("a", "self"), item("b", "project")] },
      ROLES,
    );
    expect(view.state).toBe("configured");
    expect(view.role).toBe("role-frontend");
    expect(view.truncated).toBe(true);
    expect(view.groups.map((group) => group.origin)).toEqual(["self", "project"]);
    expect(view.empty).toBe(false);
  });

  it("neznámý stav ze serveru se nevydává za zapnutou paměť", () => {
    expect(memoryModel({ status: "vymyslene" }, null).state).toBe("unknown");
  });

  it("chybějící klíče rolí jsou needs_provisioning, ne nedostupnost", () => {
    const view = memoryModel(
      { status: "needs_provisioning", reason: "Bez klíče zůstávají role: role-db.", missingRoles: ["role-db"] },
      null,
    );
    expect(view.state).toBe("needs_provisioning");
    expect(view.reason).toBe("Bez klíče zůstávají role: role-db.");
    expect(view.empty).toBe(true);
  });
});

describe("agent-memory: rozdání klíčů rolím", () => {
  it("banner má pevný text", () => {
    expect(NEEDS_PROVISIONING_BANNER).toBe("Role zatím nemají klíče v OpenViking. Založ je jedním klikem.");
  });

  it("chybějící role z odpovědi serveru jako id", () => {
    expect(missingRoleIds({ status: "needs_provisioning", missingRoles: ["role-db", "role-frontend"] }))
      .toEqual(["role-db", "role-frontend"]);
  });

  it("cizí tvar missingRoles se čte jako žádné role, ne jako chyba", () => {
    expect(missingRoleIds(null)).toEqual([]);
    expect(missingRoleIds({ status: "needs_provisioning" })).toEqual([]);
    expect(missingRoleIds({ status: "needs_provisioning", missingRoles: "role-db" as never })).toEqual([]);
    expect(missingRoleIds({ status: "needs_provisioning", missingRoles: [1, null, "role-x"] as never })).toEqual(["role-x"]);
  });

  it("chybějící role se ukážou jménem z knihovny, neznámé id tak, jak přišlo", () => {
    expect(missingRoleLabels({ status: "needs_provisioning", missingRoles: ["role-db", "role-nic"] }, ROLES))
      .toEqual(["Databáze", "role-nic"]);
  });

  it("tělo rozdání klíčů nese jen výslovné potvrzení", () => {
    expect(provisionPayload()).toEqual({ confirmed: true });
    expect(Object.keys(provisionPayload())).toEqual(["confirmed"]);
  });

  it("bez odpovědi není co shrnovat", () => {
    expect(provisionSummary(null)).toBe("");
  });

  it("shrnutí jmenuje založené, beze změny i chyby, se jmény rolí z knihovny", () => {
    const summary = provisionSummary(
      { status: "partial", provisioned: ["role-frontend"], reused: ["role-db"], errors: [{ role: "role-x", reason: "OpenViking není dostupný." }] },
      ROLES,
    );
    expect(summary).toBe(
      "Založeno: Frontend. Beze změny, klíč už měly: Databáze. Nepodařilo se: role-x (OpenViking není dostupný.).",
    );
  });

  it("žádná změna dostane vlastní větu, ne prázdný řetězec", () => {
    expect(provisionSummary({ status: "configured", provisioned: [], reused: [], errors: [] }))
      .toBe("Rozdání klíčů rolím neudělalo žádnou změnu.");
  });
});

describe("agent-memory: volby role", () => {
  it("první volba je vždy karta bez role", () => {
    expect(roleOptions(ROLES)[0]).toMatchObject({ value: "", label: NO_ROLE_LABEL });
  });

  it("každá role z knihovny má hodnotu, popisek a větu k čemu je", () => {
    expect(roleOptions(ROLES).slice(1)).toEqual([
      { value: "role-frontend", label: "Frontend", description: "Obrazovky a dílky." },
      { value: "role-db", label: "Databáze", description: "Schéma a migrace." },
    ]);
  });

  it("role bez id se zahodí, role bez popisku se pojmenuje svým id", () => {
    expect(roleOptions([{ label: "Bez id" }, { id: "role-x" }]).slice(1)).toEqual([
      { value: "role-x", label: "role-x", description: "" },
    ]);
  });

  it("cizí tvar knihovny nechá aspoň volbu bez role", () => {
    expect(roleOptions(null)).toHaveLength(1);
  });
});

describe("agent-memory: kdy se smí číst, psát a půjčovat", () => {
  it("vybavení chce běžící paměť, roli karty a dotaz", () => {
    expect(canRecall("role-frontend", "co víš", "configured")).toBe(true);
    expect(canRecall(null, "co víš", "configured")).toBe(false);
    expect(canRecall("role-frontend", "   ", "configured")).toBe(false);
    expect(canRecall("role-frontend", "co víš", "disabled")).toBe(false);
  });

  it("zápis je vždy vědomý: uzamčená karta ani vypnutá paměť ho nedovolí", () => {
    const draft = { role: "role-frontend", kind: "note" as const, text: "poučení" };
    expect(canRemember(draft, false, "configured")).toBe(true);
    expect(canRemember(draft, true, "configured")).toBe(false);
    expect(canRemember(draft, false, "unavailable")).toBe(false);
    expect(canRemember({ ...draft, role: null }, false, "configured")).toBe(false);
  });

  it("prázdný, přerostlý ani binární text se neodesílá", () => {
    const draft = { role: "role-frontend", kind: "lesson" as const, text: "" };
    expect(canRemember(draft, false, "configured")).toBe(false);
    expect(canRemember({ ...draft, text: "x".repeat(MAX_MEMORY_TEXT) }, false, "configured")).toBe(true);
    expect(canRemember({ ...draft, text: "x".repeat(MAX_MEMORY_TEXT + 1) }, false, "configured")).toBe(false);
    expect(canRemember({ ...draft, text: "a\0b" }, false, "configured")).toBe(false);
  });

  it("neznámý druh zápisu neprojde", () => {
    expect(canRemember({ role: "role-db", kind: "vymyslene" as never, text: "a" }, false, "configured")).toBe(false);
  });

  it("půjčka se dá jen od jiné role", () => {
    expect(canLend({ fromRole: "role-db", toRole: "role-frontend", query: "index" }, "configured")).toBe(true);
    expect(canLend({ fromRole: "role-db", toRole: "role-db", query: "index" }, "configured")).toBe(false);
    expect(canLend({ fromRole: "", toRole: "role-frontend", query: "index" }, "configured")).toBe(false);
    expect(canLend({ fromRole: "role-db", toRole: "role-frontend", query: "" }, "configured")).toBe(false);
  });
});

describe("agent-memory: těla požadavků mají přesné klíče", () => {
  it("vybavení posílá právě šest polí kontraktu", () => {
    const payload = recallPayload(SCOPE, "role-frontend", "  co víš  ");
    expect(payload).toEqual({
      role: "role-frontend", project: "p1", workspace: "main", nodeId: "n1", query: "co víš", maxTokens: MEMORY_MAX_TOKENS,
    });
    expect(Object.keys(payload).sort()).toEqual(["maxTokens", "nodeId", "project", "query", "role", "workspace"]);
  });

  it("karta bez role pošle role: null a server ji dohledá sám", () => {
    expect(recallPayload(SCOPE, "", "dotaz").role).toBeNull();
  });

  it("zápis nese potvrzení člověka a nic navíc", () => {
    const payload = rememberPayload(SCOPE, { role: "role-db", kind: "decision", text: "rozhodli jsme" });
    expect(payload).toEqual({
      role: "role-db", project: "p1", workspace: "main", nodeId: "n1",
      kind: "decision", text: "rozhodli jsme", confirmed: true,
    });
  });

  it("půjčka posílá obě role, dotaz a rozpočet, nikdy projekt ani kartu", () => {
    const payload = lendPayload({ fromRole: "role-db", toRole: "role-frontend", query: " index " }, 200);
    expect(payload).toEqual({ fromRole: "role-db", toRole: "role-frontend", query: "index", maxTokens: 200 });
  });
});

describe("agent-memory: paměť z briefu a výchozí dotaz", () => {
  it("brief bez paměti role nevrací prázdný výsledek, ale nic", () => {
    expect(briefRoleMemory(null)).toBeNull();
    expect(briefRoleMemory({ context: {} })).toBeNull();
  });

  it("paměť z briefu se čte i s důvodem a rolí", () => {
    const brief = { context: { roleMemory: { status: "skipped", reason: "karta nemá roli", role: null, items: [] } } };
    expect(briefRoleMemory(brief)).toEqual({ status: "skipped", reason: "karta nemá roli", role: null, items: [] });
  });

  it("položky z briefu projdou stejným seskupením jako vybavení", () => {
    const brief = { context: { roleMemory: { status: "configured", role: "role-db", items: [item("a", "self")] } } };
    const view = memoryModel({ status: "configured" }, briefRoleMemory(brief), ROLES);
    expect(view.groups).toHaveLength(1);
    expect(view.groups[0].items[0].uri).toBe("a");
  });

  it("výchozí dotaz je cíl karty; napsaný dotaz má přednost", () => {
    const brief = { orientation: { goal: { goal: "Dodělat panel paměti" } } };
    expect(memoryQuery(brief, "n1", "")).toBe("Dodělat panel paměti");
    expect(memoryQuery(brief, "n1", "  jiný dotaz ")).toBe("jiný dotaz");
  });

  it("karta bez cíle se ptá sama na sebe, nikdy prázdným dotazem", () => {
    expect(memoryQuery({}, "n1", "")).toBe("karta n1");
    expect(memoryQuery({ goal: { goal: "Cíl z balíčku" } }, "n1", "")).toBe("Cíl z balíčku");
  });
});
