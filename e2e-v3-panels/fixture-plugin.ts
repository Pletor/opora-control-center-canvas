// Vlastní testovací fixture pro Desktop v3 panely (Sonnet lane).
// Implementuje smluvené API dle CONTRACT.md jako in-memory mock — NENÍ produkční backend.
import { createHash, randomUUID } from "node:crypto";
import type { Plugin, Connect } from "vite";

type JsonRecord = Record<string, unknown>;

function send(res: Connect.IncomingMessage extends never ? never : any, status: number, body: JsonRecord) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(body));
}

function readBody(req: any): Promise<JsonRecord> {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk: Buffer) => (raw += chunk));
    req.on("end", () => {
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch (e) {
        reject(e);
      }
    });
    req.on("error", reject);
  });
}

function emptyState() {
  return { settings: [], rules: [], decisions: [], nodes: {}, tickets: [] };
}

function digestOf(input: unknown): string {
  return createHash("sha256").update(JSON.stringify(input)).digest("hex");
}

type StateEntry = { revision: number; state: ReturnType<typeof emptyState> };
type SnapshotEntry = { id: string; digest: string; packet: JsonRecord; scope: { project: string; workspace: string } };
type HandoffEntry = JsonRecord & { id: string; digest: string; scope: JsonRecord; status: string };

export function fixturePlugin(): Plugin {
  const states = new Map<string, StateEntry>();
  const latestPreviewDigest = new Map<string, string>();
  const snapshots = new Map<string, SnapshotEntry>();
  const handoffs = new Map<string, HandoffEntry>();
  const timers = new Map<string, ReturnType<typeof setTimeout>>();
  const planningRuns = new Map<string, JsonRecord[]>();

  const stateKey = (project: string, workspace: string) => `${project}::${workspace}`;
  const scopeKey = (p: { project: string; workspace: string; nodeId: string; path: string; sessionId: string }) =>
    JSON.stringify([p.project, p.workspace, p.nodeId, p.path, p.sessionId]);

  return {
    name: "opora-desktop-v3-fixture",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = new URL(req.url || "", "http://127.0.0.1");
        const pathname = url.pathname;
        if (!pathname.startsWith("/api/")) return next();
        try {
          if (pathname === "/api/health") return send(res, 200, { ok: true });

          if (pathname === "/api/test/reset" && req.method === "POST") {
            states.clear();
            latestPreviewDigest.clear();
            snapshots.clear();
            handoffs.clear();
            planningRuns.clear();
            timers.forEach((t) => clearTimeout(t));
            timers.clear();
            return send(res, 200, { ok: true });
          }
          if (pathname === "/api/test/seed-planning-runs" && req.method === "POST") {
            const body = await readBody(req);
            planningRuns.set(String(body.project), (body.runs as JsonRecord[]) || []);
            return send(res, 200, { ok: true });
          }

          if (pathname === "/api/desktop-v3/state" && req.method === "GET") {
            const project = url.searchParams.get("project") || "";
            const workspace = url.searchParams.get("workspace") || "";
            if (!project || !workspace) return send(res, 400, { error: "Chybí project nebo workspace." });
            const key = stateKey(project, workspace);
            const entry = states.get(key) || { revision: 0, state: emptyState() };
            states.set(key, entry);
            return send(res, 200, { revision: entry.revision, state: entry.state, readOnly: workspace === "main" });
          }
          if (pathname === "/api/desktop-v3/state" && req.method === "POST") {
            const body = await readBody(req);
            const { project, workspace, expectedRevision, state } = body as {
              project: string;
              workspace: string;
              expectedRevision: number;
              state: JsonRecord;
            };
            if (!project || !workspace || typeof expectedRevision !== "number" || typeof state !== "object")
              return send(res, 400, { error: "Neplatný požadavek." });
            if (workspace === "main") return send(res, 403, { error: "Main je pouze pro čtení." });
            const key = stateKey(project, workspace);
            const entry = states.get(key) || { revision: 0, state: emptyState() };
            if (entry.revision !== expectedRevision)
              return send(res, 409, { error: "Konflikt revizí; načtěte znovu." });
            const next = { revision: entry.revision + 1, state: state as ReturnType<typeof emptyState> };
            states.set(key, next);
            return send(res, 200, { revision: next.revision, state: next.state, readOnly: false });
          }

          if (pathname === "/api/desktop-v3/packet/preview" && req.method === "POST") {
            const body = await readBody(req);
            const { project, workspace, nodeId, path, sessionId, references, note } = body as {
              project: string;
              workspace: string;
              nodeId: string;
              path: string;
              sessionId: string;
              references: string[];
              note: string;
            };
            // sessionId is optional: an empty string means "current project/editor preview, not
            // bound to a specific run session" — it is a valid, non-random scope value.
            if (!project || !workspace || typeof sessionId !== "string")
              return send(res, 400, { error: "Neplatný rozsah balíčku." });
            const sourceManifest = (references || []).map((ref) => ({
              kind: "reference",
              ownerId: ref,
              revision: 1,
              included: true,
              reason: "explicitní reference výběru",
            }));
            const packet = {
              schema: "opora.packet/1",
              scope: { project, workspace, nodeId, path, sessionId },
              task: { note: note || "" },
              context: { referencesCount: (references || []).length },
              sourceManifest,
              warnings: (references || []).length === 0 ? ["Žádné reference nejsou přiloženy."] : [],
            };
            const digest = digestOf(packet);
            latestPreviewDigest.set(scopeKey({ project, workspace, nodeId, path, sessionId }), digest);
            return send(res, 200, { digest, packet });
          }
          if (pathname === "/api/desktop-v3/packet/snapshot" && req.method === "POST") {
            const body = await readBody(req);
            const { project, workspace, nodeId, path, sessionId, references, note, digest } = body as {
              project: string;
              workspace: string;
              nodeId: string;
              path: string;
              sessionId: string;
              references: string[];
              note: string;
              digest: string;
            };
            const key = scopeKey({ project, workspace, nodeId, path, sessionId });
            const latest = latestPreviewDigest.get(key);
            if (!latest || latest !== digest)
              return send(res, 409, { error: "Zdroje se změnily od náhledu; vytvořte nový náhled." });
            const sourceManifest = (references || []).map((ref) => ({
              kind: "reference",
              ownerId: ref,
              revision: 1,
              included: true,
              reason: "explicitní reference výběru",
            }));
            const packet = {
              schema: "opora.packet/1",
              scope: { project, workspace, nodeId, path, sessionId },
              task: { note: note || "" },
              context: { referencesCount: (references || []).length },
              sourceManifest,
              warnings: (references || []).length === 0 ? ["Žádné reference nejsou přiloženy."] : [],
            };
            const id = randomUUID();
            snapshots.set(id, { id, digest, packet, scope: { project, workspace } });
            return send(res, 200, { id, digest, packet });
          }
          const snapshotMatch = pathname.match(/^\/api\/desktop-v3\/packet\/snapshots\/([^/]+)$/);
          if (snapshotMatch && req.method === "GET") {
            const snap = snapshots.get(snapshotMatch[1]);
            const project = url.searchParams.get("project") || "";
            const workspace = url.searchParams.get("workspace") || "";
            if (!snap || snap.scope.project !== project || snap.scope.workspace !== workspace)
              return send(res, 404, { error: "Snímek nenalezen." });
            return send(res, 200, { id: snap.id, digest: snap.digest, packet: snap.packet });
          }
          const prepareMatch = pathname.match(/^\/api\/desktop-v3\/packet\/snapshots\/([^/]+)\/prepare$/);
          if (prepareMatch && req.method === "POST") {
            const snap = snapshots.get(prepareMatch[1]);
            const body = await readBody(req);
            const { project, workspace, task } = body as { project: string; workspace: string; task: string };
            if (!snap || snap.scope.project !== project || snap.scope.workspace !== workspace)
              return send(res, 404, { error: "Snímek nenalezen." });
            if (typeof task !== "string" || task.trim().length < 10)
              return send(res, 400, { error: "Zadání je příliš krátké." });
            const id = randomUUID();
            const scope = snap.packet.scope as { project: string; workspace: string; nodeId: string };
            const run: HandoffEntry = {
              id,
              digest: snap.digest,
              scope: { project: scope.project, workspace: scope.workspace, node: scope.nodeId },
              task,
              status: "prepared",
              provider: "fixture",
              model: "fixture-model",
              budgetSeconds: 60,
              contextSummary: "fixture kontext · " + snap.id,
              events: [{ kind: "prepared", observedAt: new Date().toISOString() }],
              error: null,
              verification: { passed: null },
              result: null,
            };
            handoffs.set(id, run);
            return send(res, 200, run);
          }

          const startMatch = pathname.match(/^\/api\/task-handoffs\/([^/]+)\/start$/);
          if (startMatch && req.method === "POST") {
            const run = handoffs.get(startMatch[1]);
            const body = await readBody(req);
            if (!run) return send(res, 404, { error: "Běh nenalezen." });
            if (body.digest !== run.digest || body.confirmed !== true)
              return send(res, 400, { error: "Neplatné potvrzení spuštění." });
            run.status = "running";
            (run.events as JsonRecord[]).push({ kind: "worker_started", observedAt: new Date().toISOString() });
            const timer = setTimeout(() => {
              if (run.status !== "running") return;
              const content = `# Fixture výsledek\nÚkol: ${run.task}\n`;
              run.status = "completed";
              run.verification = { passed: true };
              run.result = { content, sha256: digestOf(content) };
              (run.events as JsonRecord[]).push({ kind: "file_written", observedAt: new Date().toISOString() });
            }, 500);
            timers.set(run.id, timer);
            return send(res, 200, run);
          }
          const stopMatch = pathname.match(/^\/api\/task-handoffs\/([^/]+)\/stop$/);
          if (stopMatch && req.method === "POST") {
            const run = handoffs.get(stopMatch[1]);
            const body = await readBody(req);
            if (!run) return send(res, 404, { error: "Běh nenalezen." });
            if (body.confirmed !== true) return send(res, 400, { error: "Zastavení musí být potvrzeno." });
            const timer = timers.get(run.id);
            if (timer) clearTimeout(timer);
            run.status = "cancelled";
            (run.events as JsonRecord[]).push({ kind: "stopped", observedAt: new Date().toISOString() });
            return send(res, 200, run);
          }
          const exportMatch = pathname.match(/^\/api\/task-handoffs\/([^/]+)\/export$/);
          if (exportMatch && req.method === "GET") {
            const run = handoffs.get(exportMatch[1]);
            if (!run) return send(res, 404, { error: "Běh nenalezen." });
            return send(res, 200, { id: run.id, digest: run.digest, task: run.task, context: { fixture: true } });
          }
          const getMatch = pathname.match(/^\/api\/task-handoffs\/([^/]+)$/);
          if (getMatch && req.method === "GET") {
            const run = handoffs.get(getMatch[1]);
            if (!run) return send(res, 404, { error: "Běh nenalezen." });
            return send(res, 200, run);
          }
          if (pathname === "/api/task-handoffs" && req.method === "GET") {
            const project = url.searchParams.get("project") || "";
            const workspace = url.searchParams.get("workspace") || "";
            const runs = Array.from(handoffs.values()).filter(
              (r) => (r.scope as JsonRecord).project === project && (r.scope as JsonRecord).workspace === workspace,
            );
            return send(res, 200, { runs });
          }
          if (pathname === "/api/llm/runs" && req.method === "GET") {
            const project = url.searchParams.get("project") || "";
            return send(res, 200, { runs: planningRuns.get(project) || [], active: null });
          }
          return send(res, 404, { error: "Neznámý fixture endpoint." });
        } catch (e) {
          return send(res, 500, { error: String(e) });
        }
      });
    },
  };
}
