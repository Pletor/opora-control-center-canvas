import { describe, expect, it } from "vitest";
import { boardView, layoutBoard, when } from "./linie-board";
import { boardFixture } from "./linie-fixture";
import { ballTip, commitTip } from "./linie-tip";

const layout = layoutBoard(boardView(boardFixture));

describe("tip kuličky a commitu jedním dílkem", () => {
  it("opuštěný commit: sha · zpráva, čas, kulička, autor z vazby worktree, zdroj git log a věta o opuštění", () => {
    const dead = layout.commits.find((c) => c.abandoned)!;
    expect(commitTip(dead)).toEqual({ x: dead.x, y: dead.y, title: "deadbee · SVG popisky", rows: [
      { k: "čas", v: when("2026-11-05T10:40:00Z") }, { k: "kulička", v: "OP-3F9A1C Panel detailu karty" }, { k: "autor", v: "agent-a" },
      { k: "zdroj", v: "git log" }, { k: "opuštěno", v: "zůstává v historii, do cíle nejde" }] });
    expect(commitTip(layout.commits[0]).rows.map((r) => r.k)).not.toContain("opuštěno");
  });
  it("kulička: nadpis a řádky bez prázdných hodnot", () => {
    const tip = ballTip(layout.balls.find((b) => b.ticketId === "tk_2")!);
    expect(tip.title).toBe("Datový uzel");
    expect(tip.rows.map((r) => r.k)).not.toContain("značka");
    expect(tip.rows[0]).toEqual({ k: "stav", v: "otevřeno" });
  });
});
