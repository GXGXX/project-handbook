---
name: project-handbook
description: Create a self-contained, evidence-aware offline handbook from a codebase and its documentation. Use when a user asks to turn project knowledge into a readable website, onboarding guide, or codebase book; do not use for ordinary README edits, API reference generation, or general website work.
metadata:
  version: "0.1.0"
  source-inspiration: "https://github.com/lili-luo/aicoding-cookbook"
---

# Project Handbook

Transform project knowledge into a small static site that a maintainer can open
without a server. Treat executable code as the factual baseline, keep evidence
visible, and make every build reproducible from files in the project.

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
- Prefer local SVG/PNG diagrams. Mermaid is optional: if a page includes a
  Mermaid block, provide a pinned local `assets/mermaid.min.js` and run a real
  browser check; the static verifier cannot prove Mermaid renders.

## Workflow

1. **Inventory** — locate docs, source entry points, configuration, tests, and
   deployment files. Write a short evidence map before drafting prose.
2. **Design the reading path** — organize pages by reader understanding
   (orientation, architecture, behavior, data/integration, operations,
   reference). Keep the navigation order in `book.json`.
3. **Scaffold** — run `scripts/init_handbook.py <output-dir>` and replace the
   sample config/content. Use a compact handbook for small repositories; do
   not create pages that have no evidence or reader value.
4. **Author** — write independent pages with stable headings, source paths,
   concrete commands, and an explicit drift page when needed. Keep exact names,
   ports, fields, and thresholds unchanged.
5. **Build and verify** — run `python scripts/build_handbook.py <handbook-dir>`
   followed by `python scripts/verify_handbook.py <handbook-dir>`. Fix errors;
   do not ship a warning-only partial build unless the user explicitly requests
   a draft preview and the README labels it as such.
6. **Smoke test** — open `site/index.html` in a browser, test navigation,
   search, theme switching, responsive layout, and every diagram. Report what
   was and was not rendered in the delivery notes.

## Supporting guidance

- Read [references/audit-checklist.md](references/audit-checklist.md) during
  repository inventory and fact checking.
- Read [references/authoring.md](references/authoring.md) while drafting pages.
- Read [references/validation.md](references/validation.md) before delivery.

## Included tools

- `scripts/init_handbook.py` — create a portable handbook skeleton.
- `scripts/build_handbook.py` — validate config and compile HTML pages plus a
  complete search index.
- `scripts/verify_handbook.py` — perform deterministic structural, link,
  security, and evidence checks.
