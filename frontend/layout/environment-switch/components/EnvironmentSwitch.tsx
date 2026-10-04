import { useEffect } from "react";

export type Environment = "project" | "editor" | "live";
const environments: { id: Environment; label: string; hint: string }[] = [
  { id: "project", label: "Projekt", hint: "Strom zdrojů, podstata, architektura a dokumentace · Alt+1" },
  { id: "editor", label: "Editor", hint: "Plátno, bloky, deníky, kreslení a kontext · Alt+2" },
  { id: "live", label: "Live Run", hint: "Skutečné relace, pracovní prostředí a důkazy · Alt+3" },
];

export default function EnvironmentSwitch({ value, onChange, disabled }: {
  value: Environment; onChange: (value: Environment) => void; disabled: boolean;
}) {
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (disabled || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const target = environments[Number(event.key) - 1];
      if (target) { event.preventDefault(); onChange(target.id); }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onChange, disabled]);
  return <nav className="environment-switch" aria-label="Pracovní prostředí">
    {environments.map((item) => <button type="button" key={item.id} aria-pressed={value === item.id}
      disabled={disabled} title={item.hint} onClick={() => onChange(item.id)}>{item.label}
      {item.id !== "live" && <small aria-hidden="true">{item.id === "project" ? "Aplikace a kód" : "Stavba aplikace"}</small>}</button>)}
  </nav>;
}
