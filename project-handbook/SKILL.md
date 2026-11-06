---
name: project-handbook
description: 把「这个流程/规则/数值是怎么回事」讲成一张可点击的流程图网页。Use when someone gives a folder (project code, product docs, PRD, 活动方案, 配置表) and asks how something works or is calculated — 帮我梳理登录流程、这个活动奖励怎么发、伤害怎么算、这个功能的规则是什么、新人看不懂这个系统 — including vague questions; and when someone pastes a message from a handbook page that starts with 「请用 project-handbook 技能」. Reads the folder without changing it and delivers one offline HTML flowchart with branches, formulas, worked examples and evidence; questions asked in the page are answered by you and saved back into it. Not for editing project files, writing READMEs or API references.
metadata:
  version: "3.1.0"
  source-inspiration: "https://github.com/lili-luo/aicoding-cookbook"
---

# Project Handbook

Turn one question about a project into one flowchart page, `handbook.html`,
that opens by double-click in any browser. The whole process sits on one
zoomable canvas; formulas, worked examples and evidence live inside clickable
steps. Readers ask follow-up questions in the page; the page copies the
question for them to paste back to you, and you answer and save the answer
into the page. No API key and no extra setup: you are the model.

Most readers are product, operations or design people, not programmers.

## Talking to the Reader

- Use the reader's language (usually Chinese) and plain words. Do not say
  flow.json, manifest, JSON, script, command, render, node id or repository;
  say 流程图、网页、这一步、资料文件夹.
- Do not make a newcomer name functions or narrow the question first. Ask
  only when the folder is missing or the question could mean two different
  things that change the answer; then ask one short question with choices.
- Never ask the reader to install anything or run commands. If something
  fails, fix it yourself; if you cannot, say in one sentence what is missing.
- Finish with this shape, filled in:

  ```text
  结论：<one or two sentences that answer the question>

  流程图已生成：<absolute path to handbook.html>
  双击就能用浏览器打开。点任意一步可以看细节和依据；有看不懂的地方，点右上角「问答」写下问题，
  点「复制给 AI」，再粘贴回这里发给我，我回答后会存回这份网页。

  还没确认的：<gaps, or leave this line out>
  你可能还想问：<two short follow-up questions>
  ```

## Make a Handbook

1. **Interpret.** Look through the folders read-only. Note the question, your
   reading of it, and what is in and out of scope. Pick one end-to-end path
   that answers it.
2. **Trace.** Follow the evidence, not file names.

   | From | Look for | Confirm by |
   |---|---|---|
   | Product doc, 活动方案 | rules, conditions, numbers, exceptions | the exact sentence or table cell |
   | Configuration sheet | keys, sheets, columns, defaults | the read site and the actual cell values |
   | UI entry | button, page, event, scheduled trigger | the real binding and call site |
   | Server or client code | validation, branches, calculations | the function body and its callers |
   | Result | state change, reward, message shown | the write and how it is shown |
   | Failure | early exit, rollback, retry | its own branch, a test or a log |

   For every step keep where it starts, where it goes, and whether it is
   confirmed, only stated in a document, or a gap. "Not found" is a gap, not
   proof. When documents and code disagree, put both in that step.
3. **Write the flow** following [references/flow.md](references/flow.md),
   starting from `assets/flow.example.json`: exact 是/否 branches, a `switch`
   for three or more outcomes, per-step `sources` when evidence lives
   elsewhere, explicit `connections` between sections, formulas in `lines`,
   explanation in `detail`, and at least one worked example with real numbers
   whose `path` lists the steps it passes. Record the folders you read in
   `project` (absolute paths) so later questions can look things up. Label
   teaching numbers as demonstrations.
4. **Build** into a new folder. Use the folder the reader named; otherwise
   create `流程手册-<topic>` in your working folder, never inside the folders
   you were given. Never overwrite an earlier handbook; use `-v2`, `-v3`.

   Check for Python once: `python --version`, `python3 --version`, then
   `py -3 --version` on Windows.

   - **With Python:** write the flow to a file outside the output folder, then
     run `<python> -X utf8 SKILL_DIR/scripts/build_flow.py FLOW_FILE OUTPUT`.
     It checks the flow first; fix what it reports and run again.
   - **Without Python** (common on office computers; do not install it):
     create OUTPUT, copy `SKILL_DIR/assets/viewer/handbook.html` into it
     unchanged, and write `OUTPUT/flow-data.js` as UTF-8 containing
     `window.HANDBOOK_DATA = ` followed by the flow JSON and `;`. The page checks
     the flow when opened and shows any problem instead of the chart, so
     re-read your flow against references/flow.md before delivering.

   `SKILL_DIR` is the folder this file is in.
5. **Verify.** If you can open a browser, open the page and check the whole
   chart shows, clicking a step shows the right evidence and its previous and
   next steps, each example route, and search. Then compare every path,
   condition, order and number with the evidence; a page that opens is not
   proof the explanation is right.
6. **Deliver** with the shape above. With Python, also start the live in-page
   connection in [references/flow-qa.md](references/flow-qa.md) when you can:
   in Codex always; in WorkBuddy only if `codebuddy --version` works. Then add
   one line: 「想在网页里直接问、不用复制粘贴：用这个地址打开 <url>（关掉电脑或 AI
   工具后失效，失效时双击文件照样能用复制给 AI）」. Never install anything for it.

## Answer a Question From the Page

A message starting 「请用 project-handbook 技能回答我在流程手册里的」 carries
the page path and one or more questions, each with a 问题编号. Follow
[references/answers.md](references/answers.md): read the flow beside that
page, answer from it and the project folders, save the answer to the page,
then give the same answer in the chat. A message asking to 「整理进流程图，生成新版本」
is handled in the same file.

## Rules

- The folders you are given are read-only. Never run their scripts, macros,
  builds or start commands, and never output secrets.
- Never copy private material into a public example or this skill's folder.
- The page only shows what you wrote. It never infers business relationships,
  so every arrow and number must come from your trace.

## Files

- `scripts/build_flow.py`: check the flow and build the page (needs Python).
- `assets/viewer/handbook.html`: the same page for building without Python;
  it reads `flow-data.js` and `answers.js` from its own folder.
- `scripts/save_answer.py`: save an answer into `answers.js` (needs Python).
- `scripts/flow_server.py`: optional live in-page answers through Codex or
  WorkBuddy's `codebuddy` command line.
