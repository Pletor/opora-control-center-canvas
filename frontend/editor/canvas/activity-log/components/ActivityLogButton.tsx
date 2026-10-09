// Ikonka Záznam činnosti v liště: otevírá a zavírá panel. Otevřenost drží rodič.
import Icon from "@/ui-kit/icon/components/Icon";

export default function ActivityLogButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button type="button" className="activity-log__toggle" title="Záznam činnosti: co jsem udělal já a co agenti"
      aria-label="Záznam činnosti" aria-pressed={open} aria-haspopup="dialog" aria-expanded={open}
      onClick={onToggle} data-testid="activity-log">
      <Icon name="activity" size={16} />
    </button>
  );
}
