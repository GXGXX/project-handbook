# 内容质量评测

现有测试只能说明流程图**能生成、能交互**，说明不了**讲得对不对**。这里用一个公开的开源游戏仓库出题，写好答案键，给 skill 产出的 `flow.json` 自动打分。改 SKILL.md、追踪方法、数据结构之后，重新跑一遍，就能看出变好还是变差。

## 题目

源码固定在 [Shattered Pixel Dungeon](https://github.com/00-Evan/shattered-pixel-dungeon) v4.0.2（commit `57a4e06`，约 1300 个 Java 文件），见 `sources.json`。

| 题目 | 问题 | 陷阱（容易写错的地方） |
|---|---|---|
| `spd-melee-damage` | 近战攻击一次，最后打到怪身上的伤害是怎么算出来的？ | 护甲值一开始就掷出，但要等倍率和 defenseProc 之后才减；易伤 ×1.33 在减护甲之后 |
| `spd-hit-check` | 攻击时是怎么判定命中还是闪避的？ | 先判无限闪避，所以必闪压过必中；必闪时不掷骰 |
| `spd-loot-drop` | 怪物死了以后，掉不掉东西、掉什么是怎么决定的？ | 等级超限时连财富戒指额外掉落也没有；被偷、没掷中都不影响财富戒指判定 |

每道题的 `cases/<id>.json` 里写着答案键和源码出处（文件和行号），`gold/<id>.flow.json` 是满分的参考答案，也可以当作好答案的样子来看。

## 怎么跑一次

1. 拉源码（会放到 `evals/.sources/`，不进 Git）：

   ```text
   python evals/fetch_sources.py
   ```

2. 在 Codex 里装好要测的 skill 版本，开一个**新会话**，原样发：

   ```text
   使用 $project-handbook。

   这是代码目录：<上一步打印的 source root>

   近战攻击一次，最后打到怪身上的伤害是怎么算出来的？
   ```

   每道题单独开一个新会话。不要把 `evals/` 目录给 agent，它不能看到答案键。

3. 把输出目录里的 `flow.json` 复制到 `evals/runs/<题目 id>/<日期>-<说明>.flow.json`，比如 `evals/runs/spd-loot-drop/2026-11-03-v1.5.0.flow.json`。

4. 打分：

   ```text
   python evals/score_flow.py --runs evals/runs
   python evals/score_flow.py evals/cases/spd-loot-drop.json evals/runs/spd-loot-drop/2026-11-03-v1.5.0.flow.json
   ```

   第二条会列出每一项没过的检查，`TRAP` 开头的是陷阱。

## 基线

2026-11-04，skill 1.5.0（含 #1、#2），Codex 6.1 Sol · GPT 高，每题跑 1 次：

| 题目 | 分数 | 陷阱 | 扣分原因（已人工核对） |
|---|---|---|---|
| spd-melee-damage | 98.6 | 3/3 | 易伤和 attackProc 合在一个节点，没画出先后 |
| spd-hit-check | 100 | 2/2 | — |
| spd-loot-drop | 94.5 | 3/3 | 没提药水和卷轴可能变成异种版本；掉落率计算和掷骰放在一个节点 |

三份输出在 `runs/<题目 id>/2026-11-04-codex-v1.5.0.flow.json`。人工核对时还发现两件打分看不到的事：

- 伤害题比参考答案更深，补上了怪物子类改写 damage、精英怪承伤倍率和护盾；它还指出 defenseProc 返回负数时不会扣血，参考答案原来写错了，已改正。
- 掉落页面上追问「dropBonus 由哪几项组成」，回答是证据不足：页面内的关键词检索只取回了文件头和 import 行，漏掉了 Mob.java 里的 `lootChance()`。回答没有编造，但检索需要改进。

## 页面追问的源码检索

追问时如果流程图里的说明不够，模型会请求一次关键词检索，由本地服务在授权目录里查找。`retrieval/spd.json` 有 17 道检索题，每题写的是模型会发出的检索词，以及结果里必须出现的文件和行号。

```text
python evals/score_retrieval.py <fetch_sources.py 打印的 source root>
```

| 版本 | 找到 | 排第 1 |
|---|---|---|
| 旧版（只按文件名挑 400 个文件读、每个文件取命中最多的一行） | 9/17 | 5 |
| 2.0（读全部文件、忽略 import、罕见词加权、定义加分、读 Excel） | 17/17 | 13 |

旧版漏掉的大多是两种情况：真正的代码文件根本没被读到，或者被读到了却只截出 import 行。基线里「dropBonus 由哪几项组成」答不出来，就是这个原因。

## 分数怎么算

满分 100：

| 项 | 权重 | 看什么 |
|---|---|---|
| concepts | 40 | 答案键里的每个步骤，图里有没有节点讲到 |
| order | 30 | 步骤之间的先后顺序；判断节点的两条出口各自通到哪里 |
| decisions | 10 | 该画成是/否判断的地方是不是判断节点 |
| constants | 10 | 关键数值（倍率、次数）有没有出现 |
| evidence | 10 | 来源有没有写到对的文件；有没有一个完整的数值例子 |

## 局限

- 匹配靠关键词。答案键里同时列了代码名和常见中文说法，但换一种说法还是可能漏判；"不扣血"这种否定句也会被当成提到了"扣血"。分数异常时，打开报告看具体是哪一项，再对照流程图人工确认。
- 打分只看内容，不看排版。连线是否遮挡、能不能缩放，由 `tests/` 里的浏览器测试负责。
- 一道题跑一次的分数会有波动。比较两个版本时，每道题至少各跑 2 次，看平均分和陷阱通过数。
- 三道题都是 Java 单机游戏。要覆盖 Lua/C# 客户端加服务端、配置表在 Excel 里的情况，需要再找合适的公开项目补题。

## 加一道题

1. 在固定版本的源码里读清楚逻辑，写 `cases/<id>.json`：`concepts` 的 `any` 同时写代码名和中文说法；陷阱写进 `order` 并标 `"trap": true`；`evidence` 写文件和行号。
2. 写 `gold/<id>.flow.json`，确认 `python evals/score_flow.py` 给它 100 分。
3. 在 `tests/test_eval_scoring.py` 里补一个"看起来对、其实错"的变体，确认陷阱能把它扣下来。
