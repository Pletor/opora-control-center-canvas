import { lazy, Suspense } from "react";
import Intro from "./Intro";
import { showsIntro } from "../logic/entry-route";

const Workspace = lazy(() => import("@/app/components/App"));

export default function Entry() {
  if (showsIntro(window.location.search)) return <Intro />;
  return <Suspense fallback={<main className="intro intro--loading" role="status">Otevírám Oporu…</main>}><Workspace /></Suspense>;
}
