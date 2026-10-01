// TODO list bloku: každá položka má ID, zaškrtnutí a přiřazení. Koncept nové položky drží lokálně.
import { useState } from "react";
import type { Todo } from "@/shared/desktop-state/logic/types";

export default function BlockTodos({
  todos,
  disabled,
  onToggle,
  onRemove,
  onAdd,
}: {
  todos: Todo[];
  disabled: boolean;
  onToggle: (todoId: string) => void;
  onRemove: (todoId: string) => void;
  onAdd: (text: string, assignee: string) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const [assignee, setAssignee] = useState("");
  function submit() {
    const value = text.trim();
    if (!value) return;
    onAdd(value, assignee.trim()).then((ok) => {
      if (ok) {
        setText("");
        setAssignee("");
      }
    });
  }
  const done = todos.filter((t) => t.done).length;
  return (
    <section className="tree-part" aria-label="TODO bloku">
      <h5>TODO · {done} / {todos.length}</h5>
      <ul className="tree-todos">
        {todos.map((todo) => (
          <li key={todo.id} className={todo.done ? "is-done" : ""}>
            <label>
              <input type="checkbox" checked={todo.done} disabled={disabled} onChange={() => onToggle(todo.id)} />
              <span>{todo.text}</span>
            </label>
            {todo.assignee && <span className="v3-chip">{todo.assignee}</span>}
            <code className="tree-id" title="ID položky">{todo.id.slice(0, 8)}</code>
            <button type="button" aria-label="Odebrat TODO" disabled={disabled} onClick={() => onRemove(todo.id)}>✕</button>
          </li>
        ))}
      </ul>
      <div className="tree-form">
        <input aria-label="Nové TODO" placeholder="Co je potřeba udělat" value={text} disabled={disabled} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }} />
        <input aria-label="Přiřazení TODO" placeholder="komu" value={assignee} disabled={disabled} onChange={(e) => setAssignee(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }} />
        <button type="button" disabled={disabled || !text.trim()} onClick={submit}>+ TODO</button>
      </div>
    </section>
  );
}
