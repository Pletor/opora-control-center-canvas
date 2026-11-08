import { describe, expect, it } from "vitest";
import { newsCount, newsLines, primaryChoice, trialButton, trialOf, trialSentence, triedSentence } from "./linie-trial";

const A = "abc1234aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", B = "def5678bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
const trial = (extra: object = {}) => trialOf({ state: "current", url: "http://127.0.0.1:8791/", sha: A, head: A, tried: { sha: A, at: "t" }, triedCurrent: true, news: [], newsMore: 0, ...extra });

describe("zkouška v náhledu", () => {
  it("chybějící nebo rozbitý trial = none, nespadne", () => {
    for (const raw of [undefined, null, "x", { state: "jiný" }]) {
      const t = trialOf(raw);
      expect([t.state, t.tried, t.triedCurrent, t.news, t.newsMore, t.steps]).toEqual(["none", null, false, [], 0, []]);
      expect([trialSentence(t), triedSentence(t), trialButton(t).kind, primaryChoice(t)]).toEqual(["náhled neběží", "nevyzkoušeno", "start", "try"]);
    }
  });

  it("kroky Jak vyzkoušet: jen neprázdné texty", () => {
    expect(trial({ steps: ["Otevři Linii", 3, "", "Uvidíš kuličku"] }).steps).toEqual(["Otevři Linii", "Uvidíš kuličku"]);
    expect(trial({ steps: "x" }).steps).toEqual([]);
  });

  it("věta stavu pro všechny stavy", () => {
    expect(trialSentence(trial())).toBe("běží na abc1234 · aktuální");
    expect(trialSentence(trial({ state: "building" }))).toBe("staví se na abc1234");
    expect(trialSentence(trial({ state: "stale", head: B }))).toBe("zastaralý, hlava je def5678");
    expect(trialSentence(trial({ state: "failed" }))).toBe("selhal");
    expect(trialSentence(trial({ state: "none" }))).toBe("náhled neběží");
  });

  it("vyzkoušeno na A, případně s jinou hlavou", () => {
    expect(triedSentence(trial())).toBe("vyzkoušeno na abc1234");
    expect(triedSentence(trial({ head: B, triedCurrent: false }))).toBe("vyzkoušeno na abc1234, hlava je def5678");
    expect(triedSentence(trial({ tried: null, triedCurrent: false }))).toBe("nevyzkoušeno");
  });

  it("tlačítko Vyzkoušet podle stavu", () => {
    expect(trialButton(trial({ state: "none", url: null }))).toMatchObject({ kind: "start", label: "Vyzkoušet", enabled: true });
    expect(trialButton(trial({ state: "failed" }), { enabled: false, why: "blokováno" })).toMatchObject({ kind: "start", enabled: false, why: "blokováno" });
    expect(trialButton(trial())).toMatchObject({ kind: "open", enabled: true, note: "" });
    expect(trialButton(trial({ state: "stale", head: B }))).toMatchObject({ kind: "open", enabled: true, note: "zastaralý, přestaví se sám po reportu" });
    expect(trialButton(trial({ state: "building" }))).toMatchObject({ kind: "wait", label: "staví se…", enabled: false });
  });

  it("primární akce podle triedCurrent", () => {
    expect(primaryChoice(trial())).toBe("accept");
    expect(primaryChoice(trial({ triedCurrent: false }))).toBe("try");
  });

  it("novinky od poslední zkoušky s +N", () => {
    const t = trial({ news: [{ sha: B, subject: "oprava tlačítka" }, { sha: A, subject: "první" }], newsMore: 3 });
    expect(newsLines(t)).toEqual(["def5678 oprava tlačítka", "abc1234 první", "+3"]);
    expect(newsCount(t)).toBe(5);
    expect(newsLines(trial())).toEqual([]);
  });
});
