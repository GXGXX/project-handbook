---
name: project-handbook
description: Answer one reader question with one evidence-backed offline diagram handbook from client, server, and documentation directories. Use when a user asks how a flow, rule, or system works and wants a checkable HTML walkthrough; do not use for ordinary README edits, API reference generation, or general website work.
metadata:
  version: "0.9.0"
  source-inspiration: "https://github.com/lili-luo/aicoding-cookbook"
---

# Project Handbook

Default delivery is one question, one diagram. Take a reader question plus
optional client, server, and documentation roots; extract only the evidence
needed to answer that question; render a small static site a maintainer can
open without a server. Treat executable code as the factual baseline, keep
evidence visible, and do not expand into a whole-project encyclopedia unless
the user asks.

## Operating contract

- Inspect the repository before writing: inventory entry points, modules, data
  flows, configuration, operations, and external integrations.
- Classify documentation as complete, partial, stale, or absent. When docs and
  code disagree, record the disagreement instead of silently choosing a side.
- Keep the source of truth in `book.json`, `content/*.html`, and optional
  `evidence/facts.json`; never hand-edit generated `site/` pages.
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

Read [references/knowledge.md](references/knowledge.md). The default task is
not a whole-project atlas. Ask or reuse one reader question, inspect only the
client / server / documentation evidence needed to answer it, then author a
reviewed `knowledge.json` whose vertical flow, nodes and risks all serve
that question. Run `scripts/build_knowledge.py` to generate one HTML diagram
with evidence pages. File inventories are discovery drafts, not completed
explanations. Mark verified, declared, and missing runtime evidence explicitly.
A full-project map is optional thickening after the question is answered.
Never bake private project names or paths into the reusable skill; keep real
evidence outputs outside a public-ready repository.

Q&A defaults to local evidence excerpts, explicitly not model-generated answers.
Readers can opt into a configured model and confirm transmission, or copy their
question and evidence back into the installing agent. Static HTML cannot inherit
the agent's account quota. Verify conversation and draft continuity across pages.

1. **Pin the question** — write one reader question before scanning the tree.
   Everything that does not help answer it stays out of the first delivery.
2. **Inventory only what the question needs** — locate the docs, entry points,
   configuration, tests, and deployment files on that path. Write a short
   evidence map before drafting prose. Missing server code stays `open`.
3. **Design one reading path** — home vertical flowchart, primary flow, the
   nodes required by the question, risks/gaps, and source pages. Keep
   navigation in `book.json`. Do not add sibling systems “for completeness.”
4. **Scaffold or import** — for a normal repository, run
   `scripts/init_handbook.py <output-dir>` and replace the sample
   config/content. When the user provides separate client, backend, and
   documentation roots, run `scripts/import_project.py --client <client-dir>
   --backend <backend-dir> --docs <docs-dir> --output <output-dir>` only as a
   bounded evidence draft. `--backend` is optional, but omitting it must leave
   server-side conclusions explicitly open. The importer must stay read-only
   against source roots, skip VCS/cache trees, extract only bounded text and
   workbook metadata, and write the result to a new output directory outside
   sensitive source trees.
5. **Author** — keep exact names, ports, fields, and thresholds unchanged.
   Separate configuration declarations, client descriptions, checked
   references, and unknown runtime behavior.
6. **Build and verify** — run `python scripts/build_knowledge.py knowledge.json
   <new-handbook-dir>` (or `build_handbook.py` for hand-authored books)
   followed by `python scripts/verify_handbook.py <handbook-dir>`. Fix errors;
   do not ship a warning-only partial build unless the user explicitly requests
   a draft preview and the README labels it as such.
7. **Smoke test** — open the site, walk the primary flow, open one source page,
   and ask the original question in the Q&A panel. For chat, start
   `python scripts/chat_server.py <handbook-dir>` and use the printed localhost
   URL. Read [references/chat.md](references/chat.md) for relay and direct mode.

## Supporting guidance

- Read [references/audit-checklist.md](references/audit-checklist.md) during
  repository inventory and fact checking.
- Read [references/authoring.md](references/authoring.md) while drafting pages.
- Read [references/validation.md](references/validation.md) before delivery.

## Included tools

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
