---
name: project-handbook
description: Use when someone supplies client, server or docs directories and asks how a process or calculation in that project works (伤害流程是怎样的、奖励怎么发、这个数值怎么算、帮我梳理登录流程), including vague newcomer questions. Traces the directories read-only and delivers one interactive offline HTML flowchart with branches, formulas, worked examples, node evidence and in-page follow-up questions. Not for README edits, API reference generation or changing project code.
metadata:
  version: "2.1.0"
  source-inspiration: "https://github.com/lili-luo/aicoding-cookbook"
---

# Project Handbook

Deliver one flowchart for one question: a portable `handbook.html` the reader
can open anywhere, plus a local reading URL where they can ask follow-ups about
any node. The whole process sits on ONE zoomable, pannable canvas. Formulas,
worked examples and evidence live inside clickable nodes.

Do not require a newcomer to name functions or narrow their question before
inspecting the supplied directories. Ask only when ambiguity changes scope,
for example when "奖励" could mean the grant pipeline or the whole economy.

## Workflow

1. **Interpret.** Browse the supplied roots read-only. Write down the original
   question, your reading of it, what is in scope and what is not. Pick one
   end-to-end path that answers it.
2. **Trace.** Follow the evidence, not file names.
   Directory import is discovery only, never a completed explanation.

   | From | Look for | Confirm by |
   |---|---|---|
   | UI entry | button, route, event, scheduled trigger | the real binding and call site |
   | Protocol | request name, fields, return codes | sender and receiver registration match |
   | Server handler | validation, branches, business calls | the function body and its callers |
   | Configuration | keys, sheets, columns, defaults | the read site and the actual cell values |
   | Result | state change, storage, reply | the write and how the client shows it |
   | Failure | early exit, rollback, retry | its own branch, a test or a log |

   For every step keep: where it starts, where it goes, the relationship, and
   whether it is checked, only declared in docs, or a gap. Read real sheet and
   cell values for spreadsheets; a file name is not evidence. "Not found" is a
   gap, not proof that something does not exist. When docs and code disagree,
   put both in the affected node.
3. **Author** `flow.json` following [references/flow.md](references/flow.md),
   starting from `assets/flow.example.json`. Exact 是/否 branches, a `switch`
   node for three or more outcomes, per-node `sources` where a step's evidence
   lives elsewhere (a formula file, a config table), explicit cross-section
   `connections`, formulas in `lines`, explanation in `detail`,
   and at least one worked example whose trace walks the real steps and whose
   `path` lists the node ids it passes, in order, along drawn edges. Label
   teaching examples as demonstrations, not measurements. Do not add
   production notes or review summaries; keep uncertainty in the node it
   concerns.
4. **Build** with `python scripts/build_flow.py flow.json NEW_OUTPUT`. The output
   directory must not exist; earlier outputs are never replaced. When the user
   names an output directory, keep `flow.json` outside it (beside it or in a
   temporary folder) and build straight into the named directory; to rebuild
   after a fix, use a sibling such as `NAME-v2`, never a folder nested inside.
5. **Verify** in a real browser: whole canvas visible without switching, pan,
   zoom and fit, search, node details with the right evidence and matching
   previous/next steps, section titles, each example route, examples,
   cross-section arrows, edges clear of nodes, narrow layout, no network
   requests. Then compare each path, condition, order and number with the
   evidence. Structural checks do not prove the explanation is right.
6. **Deliver.** Start the follow-up connection as described in
   [references/flow-qa.md](references/flow-qa.md) and give the reader the
   local URL and the `handbook.html` path. State the deepest path you checked
   and the evidence still missing. Reading and offline export need no model;
   do not claim follow-ups work until one real answer has come back.

## Rules

- Source directories are read-only. Never run project scripts, macros, builds
  or start commands, and never output secrets.
- Never copy private input into a public example or the skill repository
  without explicit permission. Keep generated outputs outside public source.
- The renderer only shows what you authored. It never infers business
  relationships, so every edge and number must come from your trace.

## Scripts

- `scripts/build_flow.py`: validate `flow.json` and render the offline HTML.
- `scripts/flow_server.py`: serve the flow with in-page Codex follow-ups, saved
  answers, compiled versions and redacted exports.
