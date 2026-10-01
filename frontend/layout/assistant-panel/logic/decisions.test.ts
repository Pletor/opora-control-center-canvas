import { describe, expect, it } from "vitest";
import { parseDecisions } from "./decisions";

// Tvar, který skill grilling skutečně vrací (zkráceno z historie úkolu).
const GRILLING = `Teď první kolo otázek. Nic nezapisuju, ani do karty.

❓ **Q1** - **K čemu PDF slouží**: Kdo ho čte a co s ním udělá? Možnosti: (a) sdílení, (b) tisk.

➡️ (a), sdílení přehledu s lidmi mimo aplikaci. Z toho plyne, že PDF musí být srozumitelné samo o sobě.

---

❓ **Q2** - **Co se exportuje**: Celé plátno, jen aktuální vrstvu (\`layerId\`), nebo jen výběr?

➡️ Výchozí je aktuální vrstva. Když je něco vybrané, nabídnout „jen výběr“.

---

❓ **Q3** - **Obraz, nebo dokument**: Má PDF být (a) věrný obrázek plátna, nebo (b) dokument?

➡️ (a) jako první krok.

Stačí odpovědět čísly, např. \`Q1 a, Q2 ok\`.`;

describe("otázky grillingu", () => {
  it("rozpozná úvod, otázky s tématem a doporučením a závěr", () => {
    const set = parseDecisions(GRILLING);
    expect(set).not.toBeNull();
    expect(set!.intro).toBe("Teď první kolo otázek. Nic nezapisuju, ani do karty.");
    expect(set!.questions).toEqual([
      {
        id: "Q1",
        topic: "K čemu PDF slouží",
        question: "Kdo ho čte a co s ním udělá? Možnosti: (a) sdílení, (b) tisk.",
        recommendation: "(a), sdílení přehledu s lidmi mimo aplikaci. Z toho plyne, že PDF musí být srozumitelné samo o sobě.",
      },
      {
        id: "Q2",
        topic: "Co se exportuje",
        question: "Celé plátno, jen aktuální vrstvu (`layerId`), nebo jen výběr?",
        recommendation: "Výchozí je aktuální vrstva. Když je něco vybrané, nabídnout „jen výběr“.",
      },
      { id: "Q3", topic: "Obraz, nebo dokument", question: "Má PDF být (a) věrný obrázek plátna, nebo (b) dokument?", recommendation: "(a) jako první krok." },
    ]);
    expect(set!.outro).toBe("Stačí odpovědět čísly, např. `Q1 a, Q2 ok`.");
  });

  it("projde bez oddělovačů, s dlouhou pomlčkou a s „Q1.“ bez tučného písma", () => {
    const text = [
      "❓ **Q1** — **Rozsah**: Co patří dovnitř?",
      "➡️ Jen vrstva.",
      "❓ Q2. **Formát**: PDF, nebo PNG?",
      "➡ PDF.",
      "Q3. Kdo to spustí?",
      "",
      "➡️ Člověk z lišty.",
    ].join("\n");
    const set = parseDecisions(text)!;
    expect(set.intro).toBe("");
    expect(set.questions.map((q) => [q.id, q.topic, q.question, q.recommendation])).toEqual([
      ["Q1", "Rozsah", "Co patří dovnitř?", "Jen vrstva."],
      ["Q2", "Formát", "PDF, nebo PNG?", "PDF."],
      ["Q3", "", "Kdo to spustí?", "Člověk z lišty."],
    ]);
    expect(set.outro).toBe("");
  });

  it("víceřádková otázka a doporučení zůstanou celá", () => {
    const text = [
      "❓ **Q1** - **Volby**: Která varianta?",
      "- (a) první",
      "- (b) druhá",
      "",
      "➡️ (b), protože",
      "je levnější.",
      "",
      "Navíc poznámka k Q1.",
      "",
      "❓ **Q2** - **Kdy**: Hned?",
      "➡️ Ano.",
    ].join("\n");
    const [q1, q2] = parseDecisions(text)!.questions;
    expect(q1.question).toBe("Která varianta?\n- (a) první\n- (b) druhá");
    expect(q1.recommendation).toBe("(b), protože\nje levnější.\n\nNavíc poznámka k Q1.");
    expect(q2.recommendation).toBe("Ano.");
  });

  it("téma s dvojtečkou uvnitř tučného písma a otázka bez doporučení", () => {
    const set = parseDecisions("❓ **Q1** - **Rozsah:** Co dovnitř?\n\n❓ **Q2** - Bez tématu, jen otázka?")!;
    expect(set.questions).toEqual([
      { id: "Q1", topic: "Rozsah", question: "Co dovnitř?", recommendation: "" },
      { id: "Q2", topic: "", question: "Bez tématu, jen otázka?", recommendation: "" },
    ]);
  });

  it("méně než dvě otázky nebo běžný text vrací null", () => {
    expect(parseDecisions("❓ **Q1** - **Jen jedna**: otázka?\n\n➡️ ano")).toBeNull();
    expect(parseDecisions("Odpověď bez otázek.\n\n- bod")).toBeNull();
    expect(parseDecisions("Q1 a, Q2 ok, Q3 a.")).toBeNull();
    expect(parseDecisions("")).toBeNull();
  });

  it("uvnitř bloku kódu otázky nehledá", () => {
    const text = "Ukázka:\n```\n❓ **Q1** - **A**: x\n❓ **Q2** - **B**: y\n```\nKonec.";
    expect(parseDecisions(text)).toBeNull();
  });
});
