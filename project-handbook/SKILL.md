---
name: project-handbook
description: Use when a newcomer provides code and documentation directories and asks a vague project question, or needs an offline HTML explanation from framework and end-to-end flow to details, worked examples and evidence. Not for ordinary README edits or API reference generation.
metadata:
  version: "1.3.0"
  source-inspiration: "https://github.com/lili-luo/aicoding-cookbook"
---

# Project Handbook

Default delivery for a process or calculation question is a flowchart-first,
portable HTML: interpret the vague question, explain necessary background,
show actual decisions and execution order, then reveal formulas and evidence
inside clickable nodes. Show the entire process on ONE zoomable, pannable canvas.
Connect entry paths to shared processing with explicitly authored edges; never
hide the second half behind a common-process tab or next-page control.
Read [references/flow.md](references/flow.md) first and build with
`python scripts/build_flow.py flow.json NEW_OUTPUT` using the bundled
`assets/flow.example.json` schema. Never substitute a tiny overview plus a long
article for a requested flowchart. All reading navigation items need an exclusive,
visible selected state. Do not add production notes or review-summary sections
unless requested; keep factual uncertainty in the relevant node details.
For a broader conceptual handbook rather than a process question, consult
[references/learning.md](references/learning.md) and its `learning` manifest.
Do not require a newcomer to name functions or narrow their question before
inspecting the supplied directories. Ask only when ambiguity changes scope.

## Operating contract

For flowchart delivery, keep reviewed facts and topology in `flow.json`; use
the flow builder and its browser checks. For in-page follow-ups read
[references/flow-qa.md](references/flow-qa.md), start the local connection for the
reader, and deliver its URL alongside the portable file. This is the default
when the reader wants to ask follow-ups without leaving HTML. Never regenerate
the diagram for each question; explicit answer selection and compilation create
a new version. The `book.json`, `content/`, Q&A and
site-specific contracts below apply only when building a multi-page handbook,
not to the default standalone flowchart. Never copy private input data into a
public example without explicit authorization.

- Inspect the repository before writing: inventory entry points, modules, data
  flows, configuration, operations, and external integrations.
- Classify documentation as complete, partial, stale, or absent. When docs and
  code disagree, record the disagreement instead of silently choosing a side.
- For learning handbooks keep the source of truth in `knowledge.json`, including
  the reviewed `learning` content and source snapshots. Never hand-edit generated
  `handbook.html` or `site/` pages. Legacy hand-authored books use `book.json`,
  `content/*.html`, and optional `evidence/facts.json`.
- Use the bundled initializer to scaffold a handbook, the builder to generate
  pages, and the verifier to fail on broken links, missing content, unsafe
  placeholders, duplicate IDs, or missing local assets.
- Keep page facts auditable: cite source paths in `book.json` and add high-risk
  constants to `evidence/facts.json` so the verifier can check that they appear
  in the claimed page.
- Use HTML fragments in `content/`. Escape generated metadata; do not add
  scripts, inline event handlers, or remote assets to content.
- Keep the Q&A panel enabled by default when readers need interactive help. The
  browser sends only retrieved handbook context and conversation history. API
  keys stay in the local relay environment or in page memory for fetch-models /
  direct mode, and never enter `book.json`, `site/`, or Git.
- For optional model-generated answers use `scripts/chat_server.py`. It serves the
  generated site, performs a transparent keyword baseline retrieval, calls an
  OpenAI-compatible `/chat/completions` endpoint, returns source metadata, and
  refuses to answer when the corpus has no useful evidence. Browser-direct mode
  is a compatibility fallback only and must be labelled as exposing a key to
  the page.
- Prefer local SVG/PNG diagrams. Mermaid is optional: if a page includes a
  Mermaid block, provide a pinned local `assets/mermaid.min.js` and run a real
  browser check; the static verifier cannot prove Mermaid renders.

## Workflow

1. **Interpret** — inspect the supplied roots read-only. Record the original
   question, your interpretation, scope, and exclusions. Add enough background
   for a newcomer rather than forcing an isolated one-question/one-diagram view.
2. **Trace** — follow the relevant entry, protocol, handler, configuration,
   state/storage changes, return path and exceptions. Keep an evidence trace
   with source locators, relationship type, status and unresolved references.
   Directory import is discovery only, never a completed business explanation.
3. **Author** — for workflow questions follow [references/flow.md](references/flow.md):
   author exact yes/no branches, shared sections, bypasses and worked examples.
   Do not use dashed lines to imply uncertain execution. For conceptual books,
   follow the six-layer contract and manifest in
   [references/learning.md](references/learning.md). Use
   `assets/learning.example.json` as a synthetic schema example, not project facts.
   Each example links its intermediate states to real authored steps. Label
   demonstrations, runtime observations, source declarations and evidence gaps.
4. **Build** — workflow: `python scripts/build_flow.py flow.json <new-output>`.
   Conceptual book: `python scripts/build_knowledge.py knowledge.json <new-output>`.
   The learning manifest produces portable `handbook.html` as well as the legacy
   site. Existing outputs are never replaced. For old manifest details consult
   [references/knowledge.md](references/knowledge.md).
5. **Verify** — flow builds validate their manifest; open the generated file
   in a real browser and test whole-canvas visibility, pan/zoom and section selection, examples, details,
   cross-section edges, correct per-node evidence, node/edge clearance and narrow layout. Compare each path to the evidence.
   For conceptual books run `python scripts/verify_handbook.py <new-output>` and
   `python scripts/verify_handbook.py <new-output>/handbook.html`. Open the actual
   portable file and check guide controls, source return, example-to-step links,
   term search, narrow layout and offline reading. Structural checks do not
   prove semantic correctness; review the original question against the answer.
6. **Deliver** — give the local reading URL and the portable HTML, state the
   deepest checked path and missing evidence. Follow [references/flow-qa.md](references/flow-qa.md)
   for the default flowchart Q&A connection. Reading and offline export do not
   require a model; do not claim live answering works until verified. On an
   unavailable connection, preserve offline reading and explain the limitation.

## Supporting guidance

- Read [references/audit-checklist.md](references/audit-checklist.md) during
  repository inventory and fact checking.
- Read [references/authoring.md](references/authoring.md) while drafting pages.
- Read [references/validation.md](references/validation.md) before delivery.

## Included tools

- `scripts/build_flow.py` — render an authored branching flowchart as one offline HTML file; no server or model configuration needed to read it.
- `scripts/flow_server.py` — serve the flow with in-page Codex follow-ups, saved answers, selected-answer revisions and redacted exports.

- `scripts/build_knowledge.py` — render reviewed diagrams, nodes, branches and source pages from a knowledge manifest.

- `scripts/init_handbook.py` — create a portable handbook skeleton.
- `scripts/import_project.py` — import separate client and docs/config roots
  into a bounded, redacted handbook draft.
- `scripts/build_handbook.py` — validate config and compile HTML pages plus a
  complete search index.
- `scripts/verify_handbook.py` — perform deterministic structural, link,
  security, and evidence checks.
- `scripts/chat_server.py` — serve the site and relay grounded questions to an
  OpenAI-compatible model without embedding credentials.
