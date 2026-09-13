import { useEffect, useMemo, useState } from "react";
import { loadSkills, saveDisabledSkills, scopeLabel, type Skill } from "@/settings/logic/skills";

/** Skills Claude Code na tomto počítači; každý lze vypnout, Opora ho pak při práci s agentem vynechá. */
export default function SkillsSection() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [disabled, setDisabled] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "saving" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    loadSkills()
      .then((state) => {
        if (!alive) return;
        setSkills(state.skills);
        setDisabled(new Set(state.disabled));
        setStatus("ready");
      })
      .catch((exc: Error) => {
        if (!alive) return;
        setError(exc.message);
        setStatus("error");
      });
    return () => {
      alive = false;
    };
  }, []);

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const visible = skills.filter((item) => !needle || (item.name + " " + item.description).toLowerCase().includes(needle));
    const map = new Map<string, Skill[]>();
    for (const item of visible) {
      const list = map.get(item.scope) ?? [];
      list.push(item);
      map.set(item.scope, list);
    }
    return [...map.entries()];
  }, [skills, query]);

  async function toggle(id: string, enabled: boolean) {
    const next = new Set(disabled);
    if (enabled) next.delete(id);
    else next.add(id);
    setDisabled(next);
    setStatus("saving");
    try {
      const saved = await saveDisabledSkills([...next]);
      setDisabled(new Set(saved));
      setStatus("ready");
    } catch (exc) {
      setError((exc as Error).message);
      setStatus("error");
    }
  }

  const enabledCount = skills.length - [...disabled].filter((id) => skills.some((item) => item.id === id)).length;

  return (
    <section className="settings-section" aria-labelledby="skills-title">
      <h3 id="skills-title">Skills</h3>
      <p className="muted">
        Vše, co má Claude Code na tomto počítači k dispozici. Vypnutý skill Opora při práci s agentem nepoužije.
        {status !== "loading" && skills.length > 0 && <> Zapnuto {enabledCount} z {skills.length}.</>}
      </p>
      <div className="skills-toolbar">
        <input type="search" placeholder="Hledat skill" aria-label="Hledat skill" value={query} onChange={(e) => setQuery(e.target.value)} />
        <span className="muted" role="status">
          {status === "loading" && "Načítám katalog…"}
          {status === "saving" && "Ukládám…"}
          {status === "error" && error}
        </span>
      </div>
      {status !== "loading" && skills.length === 0 && <p className="muted">Žádný skill nebyl nalezen.</p>}
      {groups.map(([scope, items]) => (
        <div key={scope} className="skills-group">
          <div className="menu-head">{scopeLabel(scope)} · {items.length}</div>
          <ul className="skills">
            {items.map((item) => {
              const enabled = !disabled.has(item.id);
              return (
                <li key={item.id} className={"skill" + (enabled ? "" : " off")}>
                  <div className="skill-body">
                    <strong>{item.name}</strong>
                    <span title={item.path}>{item.description || "Bez popisu."}</span>
                  </div>
                  <label className="skill-switch">
                    <input type="checkbox" checked={enabled} disabled={status === "saving"} onChange={(e) => toggle(item.id, e.target.checked)} />
                    {enabled ? "Používat" : "Vypnuto"}
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </section>
  );
}
