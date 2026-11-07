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

/** Testovací odpověď `GET /api/pletor/linie/board` podle skici: pevné Main a Develop, téma, práce se dvěma kuličkami, oprava. */
export const boardFixture = {
  mapping: { main: "main", develop: "develop" },
  rows: [
    { id: "main", name: "Main", type: "main", ticketId: null, branch: "main", base: null, target: null, collapsed: false, order: 0, fixed: true },
    { id: "develop", name: "Develop", type: "develop", ticketId: null, branch: "develop", base: null, target: null, collapsed: false, order: 1, fixed: true },
    { id: "row_t", name: "Knihovna prvků", type: "items", ticketId: null, branch: "topic/knihovna", parent: "develop", depth: 2, base: { branch: "develop", sha: "d1" }, target: "develop", collapsed: false, order: 2 },
    { id: "row_k", name: "Komponenty", type: "work", ticketId: null, branch: null, base: { branch: "topic/knihovna", sha: "t1" }, target: "topic/knihovna", collapsed: false, order: 3 },
    { id: "row_f", name: "Řešení", type: "fix", ticketId: null, branch: "fix/popis", base: null, target: "develop", collapsed: true, order: 4 },
  ],
  balls: [
    { ticketId: "tk_1", mark: "OP-3F9A1C", rowId: "row_k", title: "Panel detailu karty", state: "accepted_unmerged", stateLabel: "hotovo, ještě nezačleněno", branch: "feat/detail-karty", headSha7: "9c8050f",
      createdAt: "2026-11-05T10:00:00Z", mergedAt: null, counts: { commits: 3, prs: 1, merges: 0 },
      links: [{ to: "tk_2", kind: "follows" }, { to: "row_t", kind: "planned" }],
      // L7a: pět os, souhrn z jednoho vyhodnocení, akce a důkazy (docs/navrhy/2026-11-06-linie-rebrand.md §4)
      axes: {
        work: { state: "submitted", src: "linie report" },
        checks: { state: "passed", sha: "9c8050f1a2b3", src: "CI" },
        acceptance: { state: "accepted", sha: "9c8050f1a2b3", src: "záznam přijetí" },
        integration: { state: "none", target: "", sha: "", at: "", mode: "", src: "merge log" },
        deploy: { envs: {}, src: "událost prostředí" },
      },
      summary: { key: "accepted", text: "přijato, čeká na začlenění 9c8050f", reason: "checks.passed(HEAD) & acceptance.accepted(HEAD) & integration.none", next: "Služba začlení do topic/knihovna (znovu ověří)." },
      allowed: ["allow_merge", "block", "preview", "revoke_accept"], blocked: { accept: "acceptance.accepted(HEAD) – už přijato", merge: "mergeAllowed chybí – nejdřív povolit začlenění" }, incomplete: ["prs"],
      evidence: [
        { kind: "commit", ref: "1f0c2aa", at: "2026-11-05T10:20:00Z", src: "git log" },
        { kind: "commit", ref: "9c8050f", at: "2026-11-05T11:00:00Z", src: "git log" },
        { kind: "check", ref: "CI #41", at: "2026-11-05T11:05:00Z", src: "CI" },
      ],
      // L7c: poslední známý PR po výpadku GitHubu, commity s opuštěným; L7d: vazba na plán a fronty
      pr: { number: 7, state: "OPEN", url: "https://x/pr/7", unconfirmed: true, ticketIds: ["tk_1"] },
      commits: [
        { sha: "1f0c2aa000", sha7: "1f0c2aa", title: "základ panelu", at: "2026-11-05T10:20:00Z", mark: "OP-3F9A1C", abandoned: null },
        { sha: "deadbee000", sha7: "deadbee", title: "SVG popisky", at: "2026-11-05T10:40:00Z", mark: "OP-3F9A1C", abandoned: { why: "SVG text neumí popisky", at: "2026-11-05T10:50:00Z", by: "agent:a1" } },
        { sha: "9c8050f1a2b3", sha7: "9c8050f", title: "ověřený panel", at: "2026-11-05T11:00:00Z", mark: "OP-3F9A1C", abandoned: null },
      ],
      plan: { state: "linked", planCardId: "card_p1", directionCardId: "card_d1", cardRevision: 3, issued: { cardId: "card_p1", cardRevision: 2, at: "2026-11-05T10:00:00Z" }, text: "plán card_p1 R3", diff: true },
      queues: ["gitQueue"] },
    { ticketId: "tk_2", rowId: "row_k", title: "Datový uzel", state: "open", stateLabel: "otevřeno", branch: "feat/datovy-uzel", headSha7: "288491d",
      createdAt: "2026-11-05T10:30:00Z", mergedAt: null, counts: { commits: 4, prs: 0, merges: 0 }, links: [{ to: "row_t", kind: "planned" }], queues: ["officeTasks"] },
    { ticketId: "tk_3", rowId: "row_t", title: "Kostra knihovny", state: "merged", stateLabel: "začleněno", branch: "topic/knihovna", headSha7: "6b0e4f2",
      createdAt: "2026-11-04T10:00:00Z", mergedAt: "2026-11-06T10:00:00Z", counts: { commits: 2, prs: 1, merges: 1 }, links: [{ to: "develop", kind: "merged" }],
      pr: { number: 5, state: "MERGED", url: "https://x/pr/5" }, queues: [] },
    { ticketId: "tk_4", rowId: "row_f", title: "Oprava: ukládání popisu", state: "blocked", stateLabel: "blokováno", branch: "fix/popis", headSha7: null,
      createdAt: "2026-11-06T09:00:00Z", mergedAt: null, counts: { commits: 0, prs: 0, merges: 0 }, links: [], queues: ["humanDecisions"] },
  ],
  realMerges: [{ sha: "abcdef0123", target: "main", parents: ["a", "b"], at: "2026-11-03T10:00:00Z", title: "develop → main" }],
  // L7c: tag na commitu kuličky, worktree s vazbou relace i bez ní, nasazení z prostředí
  tags: [{ name: "v0.9.3", sha: "1f0c2aa000", at: "2026-11-05T10:25:00Z", annotated: false }],
  worktrees: [
    { path: "C:/wt/a", branch: "feat/detail-karty", sha: "9c8050f1a2b3", binding: { ticketId: "tk_1", attempt: "run_1", agent: "agent-a", from: "2026-11-05T10:10:00Z", to: null, heartbeat: "2026-11-06T10:00:00Z", live: true } },
    { path: "C:/wt/b", branch: "feat/detail-karty", sha: "9c8050f1a2b3", binding: null },
  ],
  deploy: { envs: { staging: { sha: "abcdef0123", at: "2026-11-05T12:00:00Z", origin: "environment", by: "agent:deploy" } } },
  queues: { plansWaiting: 2, ticketsTodo: 0, humanDecisions: 1, officeTasks: 1, gitQueue: 1 },
  // L7a: čas sestavení snímku a čas posledního úspěšného čtení každého zdroje zvlášť (GitHub neodpověděl)
  snapshot: {
    id: "snap_28", builtAt: "2026-11-06T10:05:00Z",
    sources: {
      git: { verifiedAt: "2026-11-06T10:04:00Z", ok: true }, prs: { verifiedAt: "2026-11-06T09:40:00Z", ok: false },
      checks: { verifiedAt: "2026-11-06T10:03:00Z", ok: true }, sessions: { verifiedAt: "2026-11-06T10:02:00Z", ok: true }, deploy: { verifiedAt: "", ok: true },
    },
  },
};
