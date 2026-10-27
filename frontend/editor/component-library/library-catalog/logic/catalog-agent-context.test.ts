import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { agentContextViolations, CARD_FILL_FIELDS, ERROR_STATES, hasErrorState, isRepoPath, type AgentContextItem } from "./catalog-agent-context";

const backend = (path: string) => readFileSync(fileURLToPath(new URL(`../../../../../backend/${path}`, import.meta.url)), "utf-8");
const rules = (item: Omit<AgentContextItem, "id">, exists?: (path: string) => boolean) =>
  agentContextViolations({ id: "x", ...item }, exists).map((violation) => violation.rule);

describe("catalog-agent-context – zrcadlo backendu", () => {
  it("povolená pole fill jsou přesně CARD_FILL_FIELDS validátoru karty", () => {
    const tuple = /CARD_FILL_FIELDS = \(([^)]*)\)/.exec(backend("canvas/card_agent_context.py"))![1];
    expect([...tuple.matchAll(/"([^"]+)"/g)].map((match) => match[1])).toEqual([...CARD_FILL_FIELDS]);
  });

  it("stavy chyby jsou přesně ERROR_STATES kontroly mapy", () => {
    const set = /ERROR_STATES = frozenset\(\{([^}]*)\}\)/.exec(backend("project/architecture/map_check.py"))![1];
    expect([...set.matchAll(/"([^"]+)"/g)].map((match) => match[1]).sort()).toEqual([...ERROR_STATES].sort());
  });
});

describe("catalog-agent-context – lint", () => {
  it("položka bez kontextu je v pořádku", () => {
    expect(rules({})).toEqual([]);
  });

  it("tech 1–80 znaků bez okrajových mezer", () => {
    expect(rules({ tech: "React" })).toEqual([]);
    expect(rules({ tech: "" })).toEqual(["tech"]);
    expect(rules({ tech: " React" })).toEqual(["tech"]);
    expect(rules({ tech: "x".repeat(81) })).toEqual(["tech"]);
  });

  it("states 1–8 různých stavů po 1–40 znacích", () => {
    expect(rules({ states: ["chyba", "hotovo"] })).toEqual([]);
    expect(rules({ states: [] })).toEqual(["states"]);
    expect(rules({ states: Array.from({ length: 9 }, (_, i) => `s${i}`) })).toEqual(["states"]);
    expect(rules({ states: ["Hotovo", "hotovo"] })).toEqual(["states"]);
    expect(rules({ states: ["y".repeat(41)] })).toEqual(["states"]);
  });

  it("výstupní port command vyžaduje stav chyby, vstupní ne", () => {
    const send = { id: "odeslani", direction: "out" as const, carries: "command" as const };
    expect(rules({ ports: [send] })).toEqual(["states"]);
    expect(rules({ ports: [send], states: ["odesílá", "hotovo"] })).toEqual(["states"]);
    expect(rules({ ports: [send], states: [" Selhání ".trim(), "hotovo"] })).toEqual([]);
    expect(rules({ ports: [{ ...send, direction: "in" }] })).toEqual([]);
    expect(hasErrorState(["Error"])).toBe(true);
  });

  it("porty mají unikátní platné id, směr in/out a známý druh toku", () => {
    const port = { id: "a", direction: "in" as const, carries: "data" as const };
    expect(rules({ ports: [port, { ...port }] })).toEqual(["ports"]);
    expect(rules({ ports: [{ ...port, id: "a b" }] })).toEqual(["ports"]);
    expect(rules({ ports: [{ ...port, carries: "flow" as never }] })).toEqual(["ports"]);
    expect(rules({ ports: [{ ...port, direction: "both" as never }] })).toEqual(["ports"]);
  });

  it("fetch: relativní cesty v repozitáři, u dokumentu i https; existenci ověří exists", () => {
    expect(rules({ fetch: { files: ["a/b.ts"], docs: ["https://example.org/x", "docs/a.md"] } })).toEqual([]);
    expect(rules({ fetch: { files: ["../a.ts"], docs: [] } })).toEqual(["fetch"]);
    expect(rules({ fetch: { files: ["https://example.org/x"], docs: [] } })).toEqual(["fetch"]);
    expect(rules({ fetch: { files: ["a.ts", "a.ts"], docs: [] } })).toEqual(["fetch"]);
    expect(rules({ fetch: { files: ["chybi.ts"], docs: [] } }, () => false)).toEqual(["fetch"]);
    expect(isRepoPath("/etc/passwd") || isRepoPath("a\\b") || isRepoPath(".git/config") || isRepoPath("C:/a")).toBe(false);
  });

  it("fill jen z povolených polí karty, bez duplicit a ne prázdný", () => {
    expect(rules({ fill: ["sourceRef", "spec.acceptance"] })).toEqual([]);
    expect(rules({ fill: [] })).toEqual(["fill"]);
    expect(rules({ fill: ["name"] })).toEqual(["fill"]);
    expect(rules({ fill: ["text", "text"] })).toEqual(["fill"]);
  });
});
