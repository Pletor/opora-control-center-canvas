import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { createPoller } from "@/shared/hooks/logic/poller";

export type SessionView = { structureCollapsed?: import("@/layout/structure-panel/logic/layer-list").LayerGroupId[]; selection: string[]; viewport: { x: number; y: number; zoom: number } | null; filter: string };
type Handle = { sessionId: string; attachmentId: string; secret: string };
type Intent = { revision: number; view: SessionView; renderEpoch: number; applied: boolean };
type Session = { sessionId: string; createdAt: string };
const endpoint = "/api/canvas-view-attachments";

/** The secret belongs only to this tab; neither intent nor acknowledgement writes shared Canvas data. */
export function useSessionView(scope: { project: string; workspace: string } | undefined, apply: (view: SessionView) => Promise<boolean>) {
  const project = scope?.project ?? "", workspace = scope?.workspace ?? "";
  const key = "canvas-view-tab:" + JSON.stringify([project, workspace]);
  const [handle, setHandle] = useState<Handle | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [message, setMessage] = useState("");
  const [applied, setApplied] = useState(false);
  const run = useRef(apply); run.current = apply;
  const last = useRef<number | null>(null);
  const generation = useRef(0);
  const renderGeneration = useRef(0);
  const attaching = useRef(false);
  const ownsBrowser = useRef(false);
  const scopeKey = useRef(key); scopeKey.current = key;
  const post = (action: string, owned: Handle, extra = {}) => api<Intent>(endpoint + "/" + action, { project, workspace, ...owned, ...extra });
  const current = useRef({ post, handle }); current.current = { post, handle };
  const refresh = () => api<{ sessions: Session[] }>(endpoint + "/sessions?" + new URLSearchParams({ project, workspace }))
    .then(value => { if (scopeKey.current === key) setSessions(value.sessions); }).catch(error => { if (scopeKey.current === key) setMessage(String(error)); });

  useEffect(() => {
    setHandle(null); setApplied(false); last.current = null;
    if (!project || !workspace) return;
    void refresh();
    try { const saved = sessionStorage.getItem(key); if (saved) setHandle(JSON.parse(saved)); } catch { sessionStorage.removeItem(key); }
    return () => { generation.current++; };
  }, [project, workspace]);

  useEffect(() => {
    if (!handle) return;
    const epoch = ++generation.current;
    let stopped = false;
    let ownsTab = false;
    ownsBrowser.current = false;
    let duplicate = false;
    const instance = crypto.randomUUID();
    const channel = new BroadcastChannel("opora-canvas-tab-attachment");
    channel.onmessage = event => {
      const message = event.data;
      if (message.attachment !== handle.attachmentId) return;
      if (message.type === "probe" && ownsTab) channel.postMessage({ type: "occupied", attachment: handle.attachmentId, target: message.instance });
      if ((message.type === "probe" || message.type === "contender") && !ownsTab) {
        if (typeof message.instance === "string" && message.instance < instance) duplicate = true;
        if (message.type === "probe") channel.postMessage({ type: "contender", attachment: handle.attachmentId, instance });
      }
      if (message.type === "occupied" && message.target === instance) duplicate = true;
    };
    channel.postMessage({ type: "probe", attachment: handle.attachmentId, instance });
    const valid = () => !stopped && generation.current === epoch;
    const execute = async (intent: Intent) => {
      if (!valid() || last.current === intent.revision) return;
      setApplied(false);
      last.current = intent.revision;
      const renderTicket = ++renderGeneration.current;
      const rendered = await run.current(intent.view);
      if (!valid() || renderTicket !== renderGeneration.current) return;
      if (!rendered) { setMessage("Požadovaný pohled není v této vrstvě dostupný. Otevřete správnou vrstvu a zvolte Použít znovu."); return; }
      const result = await post("ack", handle, { revision: intent.revision, view: intent.view, renderEpoch: intent.renderEpoch });
      if (valid()) { setApplied(result.applied); setMessage(result.applied ? "Pohled srdce zobrazen v této kartě." : "Čeká na zobrazení."); }
    };
    const poll = async () => {
      try { const intent = await post("poll", handle); if (valid()) { setApplied(intent.applied); await execute(intent); } }
      catch (error) { if (valid()) { setApplied(false); setMessage(String(error)); } }
    };
    const poller = createPoller({ run: poll, intervalMs: 2000, immediate: false });
    // Reload invalidates any earlier UI acknowledgement before applying a saved intent again.
    const initialize = setTimeout(() => {
      if (!valid()) return;
      if (duplicate) { sessionStorage.removeItem(key); setHandle(null); setMessage("Toto připojení již používá jiná karta. Vyberte vlastní relaci."); return; }
      ownsTab = true;
      ownsBrowser.current = true;
      void post("pending", handle).then(intent => { if (valid()) return execute(intent); })
        .catch(error => { if (valid()) setMessage(String(error)); })
        .finally(() => { if (valid()) poller.start(); });
    }, 150);
    return () => {
      stopped = true; clearTimeout(initialize); poller.stop(); channel.close(); generation.current++;
      ownsBrowser.current = false;
      if (ownsTab) void post("pending", handle).catch(() => undefined);
    };
  }, [handle, project, workspace]);

  const attach = async (sessionId: string) => {
    if (handle || attaching.current) return;
    attaching.current = true;
    const ticket = generation.current;
    try {
      const saved = await api<Handle>(endpoint + "/attach", { project, workspace, sessionId });
      const owned = { sessionId: saved.sessionId, attachmentId: saved.attachmentId, secret: saved.secret };
      if (scopeKey.current !== key || generation.current !== ticket) {
        await post("detach", owned);
        return;
      }
      sessionStorage.setItem(key, JSON.stringify(owned)); last.current = null; setHandle(owned); setMessage("Připojeno; čeká na zobrazení.");
    } catch (error) { if (scopeKey.current === key && generation.current === ticket) setMessage(String(error)); }
    finally { attaching.current = false; }
  };
  const detach = async () => {
    generation.current++;
    const old = handle;
    setHandle(null); setApplied(false); last.current = null; sessionStorage.removeItem(key);
    if (old) { try { await post("detach", old); } catch (error) { setMessage(String(error)); } }
  };
  const changed = () => {
    const owned = current.current.handle;
    if (!owned || !ownsBrowser.current) return;
    renderGeneration.current++;
    setApplied(false); setMessage("Pohled jste změnili ručně; srdce jej nyní nemá potvrzený.");
    void current.current.post("pending", owned).catch(error => setMessage(String(error)));
  };
  const retry = () => { last.current = null; setMessage("Čeká na opětovné zobrazení."); };
  return { attached: !!handle, sessionId: handle?.sessionId, sessions, applied, message, attach, detach, refresh, changed, retry };
}
