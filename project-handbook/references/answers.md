# Questions From the Page

The page cannot reach your model. When the reader asks something in the page,
it copies a message like this for them to paste to you:

```text
请用 project-handbook 技能回答我在流程手册里的这个问题，并把回答存回手册。
手册：D:/资料/流程手册-活动奖励/handbook.html
问题编号：q-20261105-093321-04hp
针对：奖励是否已领取？（节点 claimed）
问题：领过一次的人再完成任务还会发吗？
```

`针对` is `整个流程` when the question is about the whole chart.

Readers may ask several questions before pasting. Then the message says
「这 N 个问题」 and lists numbered blocks, each with its own 问题编号, 针对 and
问题. Every copy carries all questions not yet answered, so a question you
already saved may appear again: skip any 问题编号 already in `answers.js`.

## Answer

1. Open the folder that holds that `handbook.html`. If it is not on this
   computer, say so plainly and ask where the file is now.
2. Read the flow: `flow.json` (built with Python) or `flow-data.js` (built
   without; the JSON after `window.HANDBOOK_DATA =`). `project` lists the
   folders it was made from; each node's `sources` point to the evidence.
3. Answer the question for that node. Look in the project folders again
   (read-only) when the flow does not settle it. Write for a non-technical
   reader: the direct answer first, then the reason, with real numbers.
   Say what you could not confirm. Markdown is fine: short lists, **bold**,
   tables. Links and images are not shown.
4. Save each answer, then reply in the chat with the same answers (numbered
   when there are several) and:
   「已存回手册，回到网页几秒后会自动显示；没出现就刷新一下。」

## Save

With Python, write the question and answer to two UTF-8 text files, then:

```text
python -X utf8 SKILL_DIR/scripts/save_answer.py HANDBOOK_DIR --id q-20261105-093321-04hp --node claimed --question-file q.txt --answer-file a.md
```

Leave out `--node` for a whole-flow question. Saving the same id again
replaces that answer.

Without Python, edit `HANDBOOK_DIR/answers.js` yourself (create it if
missing). It is one JavaScript line that assigns a JSON array; keep it valid
JSON (double quotes, `\n` for line breaks, `\"` inside text):

```js
window.HANDBOOK_ANSWERS = [
 {"id": "q-20261105-093321-04hp", "node": "claimed", "question": "领过一次的人再完成任务还会发吗？", "answer": "不会。**已领取**的人……", "time": "2026-11-05 10:12"}
];
```

Append a new object for a new id; replace the object when the id already
exists. `node` is the node id or `null`. Never put `</script>` in an answer.

## New Version From Answers

The page can also copy:

```text
请用 project-handbook 技能，把这份流程手册里下面这些已回答的问题整理进流程图，生成新版本（原版保留）。
手册：…/handbook.html
问题编号：q-…、q-…
```

Read those answers from `answers.js`, fold what they established into the
flow (node `detail`, `lines`, a new branch or example), keep `project`, and
build into a new sibling folder such as `NAME-v2` (or the next free number).
Never change the original. Tell the reader where the new page is and what
changed, in one or two sentences.

## Shared Copies

「导出离线 HTML」 makes a single file for sending to others. It contains the
chart and the chosen answers, but no project paths or source excerpts, and it
cannot ask new questions. Remind the reader that what they share may contain
internal business rules.
