import { useEffect, useRef, type ReactNode } from "react";

/** Existing feature remains responsible for content/actions; its exact selected record starts in view. */
export default function FocusedDetail({ selector, revision, children }: { selector: string; revision: string; children: ReactNode }) {
  const content = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const item = content.current?.querySelector<HTMLElement>(selector);
    const scroll = content.current?.closest<HTMLElement>(".oporahub-overview__drawer-body");
    if (item && scroll) scroll.scrollTop += item.getBoundingClientRect().top - scroll.getBoundingClientRect().top;
  }, [selector, revision]);
  return <div ref={content}>{children}</div>;
}
