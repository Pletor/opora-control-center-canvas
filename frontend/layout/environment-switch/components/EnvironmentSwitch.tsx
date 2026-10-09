import { useEffect } from "react";
import { ENVIRONMENTS, environmentForKey, type Environment } from "@/layout/environment-switch/logic/environment";

export type { Environment } from "@/layout/environment-switch/logic/environment";

export default function EnvironmentSwitch({ value, onChange, disabled }: {
  value: Environment; onChange: (value: Environment) => void; disabled: boolean;
}) {
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (disabled || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const target = environmentForKey(event.key);
      if (target) { event.preventDefault(); onChange(target); }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onChange, disabled]);
  return <nav className="environment-switch" aria-label="Pracovní prostředí">
    {ENVIRONMENTS.map((item) => <button type="button" key={item.id} aria-pressed={value === item.id}
      disabled={disabled} title={item.hint} onClick={() => onChange(item.id)}>{item.label}
      <small aria-hidden="true">{item.subtitle}</small></button>)}
  </nav>;
}
