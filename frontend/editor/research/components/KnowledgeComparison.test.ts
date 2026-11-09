import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import KnowledgeComparison, { RetrievalInfo, SolutionFacts } from "./KnowledgeComparison";
import type { KnowledgeSolution, SearchRetrieval } from "../logic/knowledge-types";

describe("existing knowledge search evidence", () => {
 it("calls an unavailable model lexical and exposes actual limits", () => {
  const value: SearchRetrieval = {requested:"hybrid",used:"lexical",candidates:140,candidatesRanked:128,candidateLimit:128,
   truncated:true,candidatePassagesTruncated:false,semantic:{status:"unavailable",model:"pinned",detail:"Worker failed"}};
  const html=renderToStaticMarkup(createElement(RetrievalInfo,{value}));
  expect(html).toContain("sémantické pořadí nebylo použito");
  expect(html).toContain("128 z 140");
  expect(html).toContain("Worker failed");
 });
 it("keeps canonical common source revision and escapes stored values", () => {
  const html=renderToStaticMarkup(createElement(KnowledgeComparison,{value:{basis:"stored",commonSources:[{projectId:"origin",workspaceId:"w",id:"source",revision:3}],
   differences:[{field:"purpose",values:[{solutionRef:{projectId:"a",nodeId:"login"},workspaceId:"w",value:"<script>unsafe()</script>"}]}]}}));
  expect(html).toContain("researchRevision=3");
  expect(html).toContain("origin");
  expect(html).not.toContain("<script>");
  expect(html).toContain("&lt;script&gt;");
 });
 it("keeps relevance separate from actual missing accepted specification", () => {
  const solution: KnowledgeSolution = {solutionRef:{projectId:"p",nodeId:"n"},snapshot:{workspaceId:"w",graphDigest:"g"},
   title:"Login",purpose:"",verification:{status:"unknown"},evidence:[],match:{score:.9,lexical:0,semantic:.9,graph:0},
   facts:{specification:null,inputs:[],inputsTruncated:false,sources:[]}};
  const html=renderToStaticMarkup(createElement(SolutionFacts,{solution}));
  expect(html).toContain("0.900");
  expect(html).toContain("Přijatá specifikace není doložena");
 });
});
