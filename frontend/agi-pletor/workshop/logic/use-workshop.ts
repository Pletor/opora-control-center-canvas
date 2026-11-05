import { useCallback, useEffect, useRef, useState } from "react";
import * as wapi from "./workshop-api";
import * as ws from "./workshop-state";

const message = (error: unknown) => (error instanceof Error ? error.message : "Požadavek selhal.");

/** React nad Dílnou: seznamy skillů a funkcí, stav dvou editorů (`workshop-state`), jedna řádka hlášení a `busy`. */
export function useWorkshop() {
  const [skills, setSkills] = useState<wapi.WorkshopSkill[]>([]);
  const [tools, setTools] = useState<wapi.WorkshopTool[]>([]);
  const [state, setStateRaw] = useState<ws.WorkshopState>(ws.EMPTY);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const current = useRef(state);
  const setState = (next: ws.WorkshopState) => { current.current = next; setStateRaw(next); };

  const run = useCallback(async (work: () => Promise<void>, done?: string) => {
    setBusy(true); setNote(null);
    try { await work(); if (done) setNote(done); } catch (error) { setNote(message(error)); } finally { setBusy(false); }
  }, []);

  const refresh = useCallback(() => run(async () => {
    const [nextSkills, nextTools] = await Promise.all([wapi.fetchSkills(), wapi.fetchTools()]);
    setSkills(nextSkills); setTools(nextTools);
  }), [run]);
  useEffect(() => { void refresh(); }, [refresh]);

  const open = (target: ws.Target) => run(async () => {
    if (target.kind === "skill") setState(ws.loadedSkill(current.current, target.name, target.path, await wapi.fetchSkillFile(target.name, target.path)));
    else { const src = await wapi.fetchTool(target.name); setState(ws.loadedTool(current.current, target.name, src.code, src.cases)); }
  });
  const go = (target: ws.Target) => { const asked = ws.askSwitch(current.current, target); setState(asked.state); if (asked.go) void open(target); };
  const skillFiles = (name: string) => skills.find((s) => s.name === name)?.files ?? [];

  return {
    skills, tools, state, note, busy, refresh,
    skillDirty: ws.skillDirty(state), toolDirty: ws.toolDirty(state),
    selectSkill: (name: string) => go({ kind: "skill", name, path: ws.defaultFile(skillFiles(name)) }),
    selectFile: (path: string) => state.skill && go({ kind: "skill", name: state.skill.name, path }),
    selectTool: (name: string) => go({ kind: "tool", name }),
    discard: () => { const done = ws.discard(current.current); setState(done.state); if (done.target) void open(done.target); },
    keep: () => setState(ws.keep(current.current)),
    editSkill: (draft: string) => setState(ws.editSkill(current.current, draft)),
    editTool: (patch: { code?: string; cases?: string }) => setState(ws.editTool(current.current, patch)),
    saveSkill: () => run(async () => {
      const doc = current.current.skill;
      if (!doc) return;
      await wapi.saveSkillFile(doc.name, doc.path, doc.draft);
      setState(ws.savedSkill(current.current, doc.draft));
    }, "Skill uložen."),
    saveTool: () => run(async () => {
      const doc = current.current.tool;
      if (!doc) return;
      await wapi.saveTool(doc.name, doc.code, doc.cases);
      setState(ws.savedTool(current.current, doc.code, doc.cases));
      setTools(await wapi.fetchTools());
    }, "Funkce uložena."),
    measure: () => run(async () => {
      const doc = current.current.tool;
      if (doc) setState(ws.measured(current.current, await wapi.measureTool(doc.name)));
    }),
    generateTool: (name: string, intent: string) => run(async () => {
      setNote("Model píše…");
      const made = await wapi.generateTool(name, intent);
      setState(ws.generated(current.current, name, made.source.code, made.source.cases, made.measure));
      setTools(await wapi.fetchTools());
    }, "Funkce vygenerována a změřena."),
    createSkill: (name: string) => run(async () => {
      await wapi.createSkill(name);
      setSkills(await wapi.fetchSkills());
      go({ kind: "skill", name, path: "SKILL.md" });
    }, `Skill ${name} založen.`),
    createTool: (name: string) => run(async () => {
      await wapi.createTool(name);
      setTools(await wapi.fetchTools());
      go({ kind: "tool", name });
    }, `Funkce ${name} založena.`),
  };
}
