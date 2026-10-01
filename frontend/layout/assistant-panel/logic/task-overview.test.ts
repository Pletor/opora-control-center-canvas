import { describe, expect, it } from "vitest";
import type { ChatItem } from "./assistant-events";
import {
  anyWorking,
  buildTasks,
  cleanTitle,
  filterTasks,
  firstLine,
  formatElapsed,
  groupTasks,
  taskGroup,
  isNewTask,
  neighbourTask,
  nextSeen,
  previewOf,
  relativeTime,
  taskStatus,
  tasksCount,
  type TaskSource,
  type TaskView,
} from "./task-overview";

const NOW = Date.parse("2026-10-01T12:00:00Z");
const ago = (minutes: number) => new Date(NOW - minutes * 60000).toISOString();
const session = (id: string, over: Partial<TaskSource> = {}): TaskSource => ({
  id, title: "", model: "opus", updatedAt: ago(10), state: "idle", ...over,
});
const answer = (text: string): ChatItem => ({ kind: "message", id: text, role: "assistant", text, streaming: false, origin: "live" });

describe("stav a čas", () => {
  it("stav session na slovo přehledu", () => {
    expect(taskStatus("running")).toBe("working");
    expect(taskStatus("waiting_approval")).toBe("waiting");
    expect(taskStatus("error")).toBe("error");
    expect(taskStatus("idle")).toBe("ready");
  });

  it("relativní čas česky", () => {
    expect(relativeTime(ago(0.2), NOW)).toBe("právě teď");
    expect(relativeTime(ago(5), NOW)).toBe("před 5 min");
    expect(relativeTime(ago(130), NOW)).toBe("před 2 h");
    expect(relativeTime(ago(60 * 30), NOW)).toBe("včera");
    expect(relativeTime(ago(60 * 24 * 3), NOW)).toBe("před 3 dny");
    expect(relativeTime(ago(60 * 24 * 6), NOW)).toBe("před 6 dní");
    expect(relativeTime("2026-09-01T10:00:00Z", NOW)).toBe("1. 9. 2026");
    expect(relativeTime("nesmysl", NOW)).toBe("");
  });
});

describe("náhled", () => {
  it("první řádek bez značek Markdownu", () => {
    expect(firstLine("\n## **Shrnutí**\ndalší")).toBe("Shrnutí");
    expect(firstLine("- `a` bod")).toBe("a bod");
    expect(firstLine("x".repeat(200), 20)).toHaveLength(20);
  });

  it("bere poslední odpověď asistenta, ne zprávu uživatele", () => {
    const items: ChatItem[] = [
      answer("Stará odpověď"),
      answer("Nová odpověď\ns detailem"),
      { kind: "message", id: "u", role: "user", text: "otázka", streaming: false, origin: "local" },
    ];
    expect(previewOf(items)).toBe("Nová odpověď");
    expect(previewOf([])).toBe("");
  });
});

describe("nové", () => {
  it("při prvním načtení není nic nové", () => {
    const sessions = [session("a"), session("b")];
    const seen = nextSeen({}, sessions, "a");
    expect(sessions.some((s) => isNewTask(s, seen, "a"))).toBe(false);
  });

  it("úkol, který doběhl jinde, je nový, dokud ho uživatel neotevře", () => {
    const seen = nextSeen({}, [session("a"), session("b", { state: "running", updatedAt: ago(3) })], "a");
    const done = session("b", { state: "idle", updatedAt: ago(1) });
    expect(isNewTask(done, seen, "a")).toBe(true);
    const opened = nextSeen(seen, [session("a"), done], "b");
    expect(isNewTask(done, opened, "b")).toBe(false);
    expect(isNewTask(done, opened, "a")).toBe(false);
  });

  it("pracující úkol není nový", () => {
    const seen = nextSeen({}, [session("b", { updatedAt: ago(5) })], null);
    expect(isNewTask(session("b", { state: "running", updatedAt: ago(1) }), seen, null)).toBe(false);
  });

  it("nextSeen vrací stejný objekt, když se nic nezměnilo", () => {
    const sessions = [session("a")];
    const seen = nextSeen({}, sessions, "a");
    expect(nextSeen(seen, sessions, "a")).toBe(seen);
  });
});

describe("buildTasks", () => {
  it("aktivní úkol bere stav a náhled z živé konverzace, ostatní z paměti panelu", () => {
    const sessions = [session("a", { title: "Plán" }), session("b", { state: "error" })];
    const tasks = buildTasks(sessions, {
      activeId: "a", activeState: "running", activeItems: [answer("Čtu plátno")], seen: {}, previews: { b: "dřív" }, now: NOW,
    });
    expect(tasks[0]).toMatchObject({ title: "Plán", status: "working", statusWord: "pracuje", preview: "Čtu plátno", active: true, when: "před 10 min" });
    expect(tasks[1]).toMatchObject({ title: "Úkol 2", status: "error", statusWord: "chyba", preview: "dřív", active: false });
    expect(anyWorking(tasks)).toBe(true);
    expect(anyWorking([tasks[1]])).toBe(false);
  });
});

describe("přepínání a název", () => {
  it("Alt+šipky jdou na sousední úkol a na krajích stojí", () => {
    const ids = ["a", "b", "c"];
    expect(neighbourTask(ids, "b", 1)).toBe("c");
    expect(neighbourTask(ids, "b", -1)).toBe("a");
    expect(neighbourTask(ids, "c", 1)).toBe("c");
    expect(neighbourTask(ids, null, 1)).toBe("a");
    expect(neighbourTask([], null, 1)).toBeNull();
  });

  it("název 1–80 znaků bez řídicích znaků", () => {
    expect(cleanTitle("  Nový\tplán  ")).toBe("Nový plán");
    expect(cleanTitle("   ")).toBeNull();
    expect(cleanTitle("x".repeat(81))).toBeNull();
    expect(cleanTitle("x".repeat(80))).toHaveLength(80);
  });
});

describe("čas tahu", () => {
  it("minuty a sekundy, nad hodinu i hodiny", () => {
    expect(formatElapsed(12_400)).toBe("0:12");
    expect(formatElapsed(185_000)).toBe("3:05");
    expect(formatElapsed(3_729_000)).toBe("1:02:09");
    expect(formatElapsed(-5)).toBe("0:00");
  });
});

describe("skupiny a hledání na celé ploše", () => {
  const view = (id: string, over: Partial<TaskView> = {}): TaskView => ({
    id, title: id, status: "ready", statusWord: "", model: "opus", when: "", preview: "", isNew: false, active: false, ...over,
  });

  it("Pracuje, Čeká na vás (nové nebo čeká na schválení), Ostatní; prázdná skupina vypadne", () => {
    const tasks = [
      view("hotovo"),
      view("běží", { status: "working" }),
      view("nová", { isNew: true }),
      view("chyba", { status: "error", isNew: true }),
      view("schválit", { status: "waiting" }),
    ];
    expect(tasks.map(taskGroup)).toEqual(["other", "working", "waiting", "other", "waiting"]);
    expect(groupTasks(tasks).map((g) => [g.label, g.tasks.map((t) => t.id)])).toEqual([
      ["Pracuje", ["běží"]],
      ["Čeká na vás", ["nová", "schválit"]],
      ["Ostatní", ["hotovo", "chyba"]],
    ]);
    expect(groupTasks([view("a")]).map((g) => g.key)).toEqual(["other"]);
    expect(groupTasks([])).toEqual([]);
  });

  it("hledá v názvech bez diakritiky a velikosti písmen, všechna slova", () => {
    const tasks = [view("Export plátna do PDF"), view("Revize mapy Archify"), view("Tmavý režim exportu")];
    expect(filterTasks(tasks, "").map((t) => t.id)).toHaveLength(3);
    expect(filterTasks(tasks, "  EXPORT ").map((t) => t.id)).toEqual(["Export plátna do PDF", "Tmavý režim exportu"]);
    expect(filterTasks(tasks, "platna pdf").map((t) => t.id)).toEqual(["Export plátna do PDF"]);
    expect(filterTasks(tasks, "rezim").map((t) => t.id)).toEqual(["Tmavý režim exportu"]);
    expect(filterTasks(tasks, "nic")).toEqual([]);
  });
});

describe("počet úkolů", () => {
  it("česky skloňuje", () => {
    expect([0, 1, 2, 4, 5].map(tasksCount)).toEqual(["0 úkolů", "1 úkol", "2 úkoly", "4 úkoly", "5 úkolů"]);
  });
});

describe("čekající schválení", () => {
  const pending: ChatItem = {
    kind: "approval",
    id: "a1",
    approval: { id: "a1", tool: "Bash", target: null, summary: "", reason: "", auto: false, status: "pending", note: "", timeout: false },
  };
  const view = { activeId: "s1", activeState: "running" as const, seen: {}, previews: {}, now: NOW };

  it("aktivní úkol s otevřenou žádostí je ve skupině Čeká na vás", () => {
    const [task] = buildTasks([session("s1", { state: "running" })], { ...view, activeItems: [pending] });
    expect(task.status).toBe("waiting");
    expect(groupTasks([task]).map((g) => g.label)).toEqual(["Čeká na vás"]);
  });

  it("rozhodnutá žádost úkol do Čeká na vás nedrží", () => {
    const done: ChatItem = { ...pending, approval: { ...(pending as Extract<ChatItem, { kind: "approval" }>).approval, status: "allowed" } };
    const [task] = buildTasks([session("s1", { state: "running" })], { ...view, activeItems: [done] });
    expect(task.status).toBe("working");
  });

  it("neaktivní úkol ve stavu waiting_approval je také v Čeká na vás", () => {
    const [task] = buildTasks([session("s2", { state: "waiting_approval" })], { ...view, activeItems: [] });
    expect(taskGroup(task)).toBe("waiting");
  });
});
