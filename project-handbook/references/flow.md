# 流程图交付

以 `assets/flow.example.json` 为可运行示例，填写经过证据追踪的清单：

- `title`、`summary`：回答用户的问题，交代必要前提。
- `graphs`：每个入口一张图；`common` 指向可选的共同流程图 ID。
- 每图含 `id`、`title`、`source`、`nodes`、`edges`。`source` 引用 `sources` 中的条目。
- 节点含 `id/title/row/col/kind/lines/detail`。`row` 从0开始；`col` 为0（主线）或1（侧线）；类型为 process、decision、terminal、merge。
- 连线含 `a/b/label/route`；route 可省略（normal）。每个判断必须恰有“是”和“否”两条出口；补充条件可写在标签空格之后。
- 主线同列向下；同一行可从主线到侧线；侧线可以向下回到主线。长跨越用 outer；绕过大段步骤用 bypass。此布局不支持任意回环或反向连线，应拆成单独子图而非勉强放置。
- `sources` 含 id、locator、excerpt；仅放必要且允许交付的摘录。来源作为文字展示，不执行。
- `examples` 含 title、provenance（演示/实测等）、input、trace（字符串数组）、result。至少覆盖正常路径和与题目有关的边界。

生成：`python scripts/build_flow.py flow.json NEW_OUTPUT`。输出目录必须不存在，防止覆盖已有成果。

阅读体验：主图先显示执行顺序，公式和依据下钻。实线不表示证据可信度；“是否验证”应写到节点详情。不要默认附加“这次改了什么”等制作过程或总结区。保留与答案有关的证据限制，但放在对应节点，而非集中成长篇说明。

验证：构建时检查 ID、引用、位置冲突、判断出口、可达性。随后用真实浏览器检查每个页签、所有选中状态、对话框、搜索、示例展开、移动端滚动和连线几何。自动结构校验不证明运行逻辑正确；必须对照原文与源码复核分支、覆盖和先后顺序。只有实际采集过运行结果才能标成实测。

发布示例使用合成或明确获准公开的内容，不能复制用户客户端、内网文档、日志或私有路径。
