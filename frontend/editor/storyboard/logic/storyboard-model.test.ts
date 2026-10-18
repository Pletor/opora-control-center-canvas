import { describe, expect, it } from "vitest";
import {
  addMomentAt, annotationSentence, duplicateMoment, interpolateState, removeAnnotation, removeMoment, serialize,
  needsAgent, openComments, setAnnotation, sortMoments, stateAt, updateMoment, validate, EASES, type Storyboard,
} from "./storyboard-model";
import { ANIMATIONS, animationOf } from "./animations";

const board = (): Storyboard => ANIMATIONS.kulicka.defaults();
const anim = animationOf("kulicka")!;

describe("stateAt", () => {
  it("interpoluje čísla podle ease předchozího momentu", () => {
    const b = board();
    // Pád 1,5 s (ease in) -> Dopad 2,3 s: v polovině u=0,5, in = 0,25.
    const s = stateAt(b, anim, 1.9);
    expect(s.y).toBeCloseTo(0.2 + (0.745 - 0.2) * 0.25, 5);
  });
  it("hold drží předchozí hodnotu až do dalšího momentu", () => {
    expect(stateAt(board(), anim, 1.0).r).toBe(0.055);
  });
  it("před prvním a po posledním momentu drží krajní stav", () => {
    const b = board();
    expect(stateAt(b, anim, -5)).toEqual(b.moments[0].state);
    expect(stateAt(b, anim, 99)).toEqual(b.moments[b.moments.length - 1].state);
  });
  it("barvy interpoluje lineárně a bool drží předchozí", () => {
    const out = interpolateState({ c: "#000000", k: true }, { c: "#ffffff", k: false }, 0.5);
    expect(out.c).toBe("#808080");
    expect(out.k).toBe(true);
  });
  it("vlastní interpolace animace má přednost", () => {
    const b = board();
    expect(stateAt(b, { interpolate: () => ({ z: 1 }) }, 2.0)).toEqual({ z: 1 });
  });
});

describe("EASES", () => {
  it("mají správné krajní body", () => {
    for (const name of ["linear", "in", "out", "inout"] as const) {
      expect(EASES[name](0)).toBe(0);
      expect(EASES[name](1)).toBeCloseTo(1, 10);
    }
    expect(EASES.hold(0.9)).toBe(0);
    expect(EASES.inout(0.5)).toBeCloseTo(0.5, 10);
  });
});

describe("úpravy momentů", () => {
  it("addMomentAt vloží moment seřazeně se stavem v daném čase", () => {
    const { board: next, index } = addMomentAt(board(), anim, 1.0);
    expect(next.moments).toHaveLength(12);
    expect(next.moments[index].t).toBe(1);
    expect(next.moments[index].state.y).toBe(0.2);
    expect(next.moments.map((m) => m.t)).toEqual([...next.moments.map((m) => m.t)].sort((a, b) => a - b));
  });
  it("updateMoment po změně t přeřadí a vrátí nový index", () => {
    const { board: next, index } = updateMoment(board(), 0, { t: 5 });
    expect(next.moments[index].t).toBe(5);
    expect(index).toBeGreaterThan(0);
  });
  it("duplicateMoment kopíruje hluboce, removeMoment nenechá prázdný storyboard", () => {
    const { board: next, index } = duplicateMoment(board(), 3);
    expect(next.moments[index].title).toContain("kopie");
    expect(next.moments[index].state).not.toBe(next.moments[3].state);
    let b = { ...board(), moments: [board().moments[0]] };
    b = removeMoment(b, 0).board;
    expect(b.moments).toHaveLength(1);
    expect(removeMoment(board(), 2).board.moments).toHaveLength(10);
  });
  it("sortMoments řadí podle t", () => {
    const b = board();
    const shuffled = { ...b, moments: [...b.moments].reverse() };
    expect(sortMoments(shuffled).moments[0].t).toBe(0);
  });
  it("anotace: přidat, nahradit, smazat; nad 20 se nepřidává", () => {
    let b = board();
    b = setAnnotation(b, 3, -1, { kind: "note", at: { x: 0.1, y: 0.2 }, text: "a" });
    b = setAnnotation(b, 3, 0, { kind: "note", at: { x: 0.1, y: 0.2 }, text: "b" });
    expect(b.moments[3].annotations).toHaveLength(1);
    expect(b.moments[3].annotations[0].text).toBe("b");
    for (let i = 0; i < 25; i++) b = setAnnotation(b, 3, -1, { kind: "note", at: { x: 0, y: 0 }, text: "" });
    expect(b.moments[3].annotations).toHaveLength(20);
    b = removeAnnotation(b, 3, 0);
    expect(b.moments[3].annotations).toHaveLength(19);
  });
});

describe("annotationSentence", () => {
  it("má stejný tvar vět jako backend", () => {
    expect(annotationSentence({ kind: "arrow", from: { x: 0.5, y: 0.72 }, to: { x: 0.56, y: 0.42 }, text: "odraz sem" }))
      .toBe("šipka z (0.50, 0.72) do (0.56, 0.42): odraz sem");
    expect(annotationSentence({ kind: "note", at: { x: 0.5, y: 0.8 }, text: "stín" })).toBe("poznámka u (0.50, 0.80): stín");
  });
});

describe("serialize", () => {
  it("drží pořadí klíčů z kontraktu a schema", () => {
    const out = serialize({ ...board(), revision: 3, updatedAt: "2026-10-16T12:00:00Z" });
    expect(Object.keys(out)).toEqual(["schema", "animation", "title", "duration", "fps", "size", "ground", "background", "moments", "revision", "updatedAt"]);
    expect(out.schema).toBe("opora.storyboard/1");
    expect(Object.keys(out.moments[0])).toEqual(["t", "title", "shows", "changes", "comment", "ease", "state", "annotations"]);
    expect(Object.keys(serialize(board()))).not.toContain("revision");
  });
  it("zachová id a skicu momentu, bez nich klíče nepřidá", () => {
    const b = board();
    b.moments[0].id = "m-3f9a1c2e";
    b.moments[0].sketch = { layer: "sb/n/m-3f9a1c2e", fileId: "abc", imageStale: true };
    const out = serialize(b);
    expect(Object.keys(out.moments[0])).toEqual(["t", "title", "shows", "changes", "comment", "ease", "state", "annotations", "id", "sketch"]);
    expect(out.moments[0].sketch).toEqual({ layer: "sb/n/m-3f9a1c2e", fileId: "abc", imageStale: true });
    expect(Object.keys(out.moments[1])).not.toContain("sketch");
  });
  it("kopie momentu nedědí id ani skicu", () => {
    const b = board();
    b.moments[0].id = "m-3f9a1c2e";
    b.moments[0].sketch = { layer: "sb/n/m-3f9a1c2e", fileId: "abc", imageStale: false };
    const copy = duplicateMoment(b, 0);
    const made = copy.board.moments[copy.index];
    expect(made.id).toBeUndefined();
    expect(made.sketch).toBeUndefined();
  });
});

describe("validate", () => {
  it("výchozí storyboardy všech animací projdou", () => {
    for (const a of Object.values(ANIMATIONS)) expect(validate(a.defaults(), Object.keys(ANIMATIONS))).toEqual([]);
  });
  it("hlásí české chyby mimo meze", () => {
    const b = board();
    b.duration = 500;
    b.moments[0].comment = "x".repeat(2001);
    b.moments[1].state = { a: Infinity };
    b.moments[2].annotations = [{ kind: "note", at: { x: 2, y: 0 }, text: "" }];
    const errors = validate(b, ["jina"]);
    expect(errors.join("|")).toContain("Neznámá animace");
    expect(errors.join("|")).toContain("Délka musí být 1–120 s.");
    expect(errors.join("|")).toContain("komentář je delší");
    expect(errors.join("|")).toContain("není konečné číslo");
    expect(errors.join("|")).toContain("mimo 0–1");
  });
  it("odmítne neseřazené momenty a prázdný seznam", () => {
    const b = board();
    expect(validate({ ...b, moments: [...b.moments].reverse() }).join()).toContain("seřazené");
    expect(validate({ ...b, moments: [] }).join()).toContain("1–200");
  });
});

describe("kód animace a workflow", () => {
  const code = { source: "export const fields = [];", title: "K", fields: [], layers: [] };
  it("serialize nese code a answered, validate hlídá kód", () => {
    const b: Storyboard = { ...board(), animation: "kod", code };
    b.moments[0].answered = false;
    const out = serialize(b);
    expect(out.code).toEqual(code);
    expect(out.moments[0].answered).toBe(false);
    expect(Object.keys(serialize(board()))).not.toContain("code");
    expect(validate(b, ["kod"])).toEqual([]);
    expect(validate({ ...b, code: undefined }, ["kod"]).join()).toContain("Chybí kód");
    expect(validate({ ...b, code: { ...code, source: "x".repeat(64001) } }, ["kod"]).join()).toContain("64 kB");
  });
  it("serialize nese scene, validate hlídá dokument scény", () => {
    const scene = { title: "S", html: "<!doctype html><html></html>", fields: [], layers: [{ id: "pozadi", label: "Pozadí" }] };
    const b: Storyboard = { ...board(), animation: "scena", scene };
    expect(serialize(b).scene).toEqual(scene);
    expect(Object.keys(serialize(board()))).not.toContain("scene");
    expect(validate(b, ["scena"])).toEqual([]);
    expect(validate({ ...b, scene: undefined }, ["scena"]).join()).toContain("Chybí dokument scény.");
    expect(validate({ ...b, scene: { ...scene, html: "x".repeat(262145) } }, ["scena"]).join()).toContain("256 kB");
  });
  it("nový komentář = neprázdný komentář bez odpovědi", () => {
    const b = board();
    b.moments[0].comment = "víc squash"; b.moments[0].answered = false;
    b.moments[1].comment = "hotovo"; b.moments[1].answered = true;
    b.moments[2].comment = "  "; b.moments[2].answered = false;
    expect(b.moments.map(needsAgent).slice(0, 4)).toEqual([true, false, false, false]);
    expect(openComments(b)).toBe(1);
  });
});
