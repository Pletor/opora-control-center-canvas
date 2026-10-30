// Vzorový `brief` požadavku z `GET /api/intake` pro testy panelu výslechu (logika i komponenty).
export const briefFixture = {
  status: "grilling",
  synthesis: {
    goal: "Provozní metriky srdce pro člověka ve Velínu.", users: "člověk, který řídí projekt",
    parts: [{ text: "cena dávky", origin: "human", source: "zadání" },
      { text: "chybovost dávek", origin: "research", source: "https://sre.google/sre-book/" },
      { text: "doba do odpovědi", origin: "derived", source: "z ceny dávky" },
      { text: "divná", origin: "x" }, { text: " ", origin: "human" }],
    acceptance: [{ text: "test_metrics projde", check: "test" }, { text: "cena dávky do 1 s", check: "measure" }, { text: "bez kontroly", check: "?" }],
    outOfScope: ["export do Grafany", ""],
  },
  questions: [
    { id: "q1", text: "Stačí denní trend?", recommended: "Ano, denní.", why: "Hodinový je drahý.", answer: "Ano, denní.", answered_at: "t", accepted: true },
    { id: "q2", text: "Kdo to čte?", recommended: "Člověk ve Velínu.", why: "Určí rozsah.", answer: null, answered_at: null },
  ],
  missing: ["outOfScope: hranice, co ne", "parts: aspoň jedna položka origin research|derived se source",
    "otázky výslechu čekají na odpověď člověka"],
};
