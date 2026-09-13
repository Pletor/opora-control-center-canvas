import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/types";
import BlockOutline, { type LinkTarget } from "@/node-detail/content/BlockOutline";
import { clearPendingEdit, editScope, readPendingEdit, usePendingFlush, writePendingEdit } from "@/shared/hooks/use-pending-edits";
import "@/canvas/natural-canvas.css";

type Entry = {
  revision: number;
  text: string;
  saved_at: string | null;
  days: { day: string; revision: number; saved_at: string }[];
  scope: { project: string; workspace: string; node: string; day: string };
};

export function today(now = new Date()) {
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

/** Deník je datovaný zápis u téhož uzlu, nikoli druhý graf ani druhý stav práce. */
export default function NodeJournal({
  project,
  workspace,
  node,
  nodeName,
  targets,
  onOpenNode,
  onAgentTask,
}: {
  project: string;
  workspace: string;
  node: string;
  nodeName: string;
  targets: LinkTarget[];
  onOpenNode?: (nodeId: string) => void;
  onAgentTask?: (text: string) => void;
}) {
  const [day, setDay] = useState(today);
  const [entry, setEntry] = useState<Entry | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const timer = useRef<number | null>(null);
  const key = editScope("node-journal", [project, workspace, node, day]);
  const pending = useRef<{ text: string; revision: number } | null>(null);
  const liveKey = useRef(key);
  liveKey.current = key;

  useEffect(() => {
    let alive = true;
    setEntry(null);
    setError("");
    setDraft(null);
    setBusy(false);
    pending.current = null;
    api<Entry>("/api/node-journal?" + new URLSearchParams({ project, workspace, node, day }))
      .then((value) => {
        if (!alive) return;
        setEntry(value);
        // Rozepsaný zápis z dřívějška patří uživateli, dokud ho server nepřevzal.
        const cached = readPendingEdit(key);
        if (cached && cached.text !== value.text) {
          pending.current = cached;
          setDraft(cached.text);
          if (cached.revision !== value.revision)
            setError("Konflikt: uložená revize se změnila. Rozepsaný zápis je zachovaný.");
        } else {
          clearPendingEdit(key);
          pending.current = null;
          setDraft(null);
        }
      })
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [key, reload]);

  // Odchod z deníku (jiný uzel, den, panel či zavření karty) čekající zápis dopíše.
  usePendingFlush(key, () => {
    if (!timer.current) return;
    window.clearTimeout(timer.current);
    timer.current = null;
    void save();
  });

  async function save() {
    const change = pending.current;
    if (!change || busy) return;
    setBusy(true);
    setError("");
    try {
      const value = await api<Entry>("/api/node-journal", {
        project,
        workspace,
        node,
        day,
        expected_revision: change.revision,
        text: change.text,
      });
      if (liveKey.current !== key) {
        clearPendingEdit(key, change);
        return;
      }
      setEntry(value);
      // Text dopsaný během ukládání zůstává rozepsaný a uloží se další revizí.
      if (pending.current && pending.current.text !== change.text) {
        pending.current = { text: pending.current.text, revision: value.revision };
        writePendingEdit(key, pending.current);
        timer.current = window.setTimeout(() => {
          timer.current = null;
          void save();
        }, 700);
      } else {
        clearPendingEdit(key, change);
        pending.current = null;
        setDraft(null);
      }
    } catch (e) {
      // Konflikt nesmí zahodit rozepsaný zápis.
      if (liveKey.current === key) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (liveKey.current === key) setBusy(false);
    }
  }

  function edit(text: string) {
    if (!entry) return;
    setDraft(text);
    pending.current = { text, revision: pending.current?.revision ?? entry.revision };
    writePendingEdit(key, pending.current);
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      timer.current = null;
      void save();
    }, 700);
  }

  const value = draft ?? entry?.text ?? "";
  const status = !entry
    ? "Načítám deník…"
    : busy
      ? "Ukládám…"
      : error
        ? "Neuloženo · chyba"
        : draft !== null
          ? "Neuložený zápis"
          : entry.revision === 0
            ? "Zatím bez zápisu"
            : `Uloženo · verze ${entry.revision}`;

  return (
    <section className="node-journal" aria-label="Deník uzlu" data-testid="node-journal">
      <header>
        <div className="eyebrow">DENÍK · {nodeName}</div>
        <label className="field inline">
          Den
          <input
            type="date"
            aria-label="Den zápisu"
            value={day}
            max="2999-12-31"
            onChange={(e) => e.target.value && setDay(e.target.value)}
          />
        </label>
        <button type="button" onClick={() => setDay(today())}>
          Dnes
        </button>
      </header>
      {error && (
        <div role="alert">
          {error}
          <button
            type="button"
            onClick={() => {
              clearPendingEdit(key);
              pending.current = null;
              setDraft(null);
              setError("");
              setReload((r) => r + 1);
            }}
          >
            Zahodit rozepsaný zápis
          </button>
        </div>
      )}
      {entry && (
        <BlockOutline
          key={key + reload}
          value={value}
          readOnly={false}
          targets={targets}
          label="Zápis dne"
          testId="journal-blocks"
          onChange={edit}
          onOpenNode={onOpenNode}
          onAgentTask={onAgentTask}
        />
      )}
      <div className="text-actions">
        <span data-testid="journal-status" role="status">
          {status}
        </span>
        <button type="button" disabled={busy || draft === null} onClick={() => save()}>
          Uložit zápis
        </button>
      </div>
      {!!entry?.days.length && (
        <ul className="journal-days" aria-label="Dny se zápisem">
          {entry.days.map((item) => (
            <li key={item.day}>
              <button
                type="button"
                className={item.day === day ? "active" : ""}
                data-testid="journal-day"
                onClick={() => setDay(item.day)}
              >
                {item.day} · verze {item.revision}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
