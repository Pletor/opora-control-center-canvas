/** Testovací odpověď `GET /api/pletor/linie/graph` podle obrázku workflow: main, develop a feat, který se vrátil do develop. */
export const linieFixture = {
  lanes: [
    { name: "main", role: "main", parent: null, sha: "m2", base: null, commits: [
      { sha: "m1", sha7: "m1", title: "start", at: "2026-11-01T10:00:00Z", parents: [] },
      { sha: "m2", sha7: "m2", title: "PR: přijaté vydání", at: "2026-11-05T10:00:00Z", parents: ["m1", "d2"] },
    ], acceptance: null, preview: null, pr: null },
    { name: "develop", role: "develop", parent: "main", sha: "d2", base: "m1", commits: [
      { sha: "d1", sha7: "d1", title: "základ", at: "2026-11-02T10:00:00Z", parents: ["m1"] },
      { sha: "d2", sha7: "d2", title: "PR: přijaté téma", at: "2026-11-04T10:00:00Z", parents: ["d1", "f2"] },
    ], acceptance: null, preview: { slug: "develop", state: "running", port: 9001, url: "http://127.0.0.1:9001", sha: "d2" }, pr: null },
    { name: "feat/detail-karty", role: "feat", parent: "develop", sha: "f2bbbbbbbb", base: "d1", commits: [
      { sha: "f1", sha7: "f1", title: "Zobrazení vybrané karty", at: "2026-11-03T10:00:00Z", parents: ["d1"] },
      { sha: "f2", sha7: "f2", title: "Ověřený panel", at: "2026-11-03T12:00:00Z", parents: ["f1"] },
    ], acceptance: { sha: "f2bbbbbbbb", target: "develop", at: "", note: "", valid: true }, preview: null, pr: { number: 7, state: "open", url: "https://x/pr/7", base: "develop" } },
  ],
  active: "feat/detail-karty",
  server: { branch: "main", sha: "m2", dirty: false },
  deployed: null,
  enforcement: "nevynuceno",
};
