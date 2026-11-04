# 其他交付格式（仅在用户明确要求时使用）

默认交付是 SKILL.md 里的单张流程图。下面两种格式只在用户要的是**这种形式**时才用，
比如“给我做一份新人入门手册”“把这些文档整理成一个可搜索的站点”。用户问“X 是怎么
算的／怎么走的”，即使问题很模糊，也仍然走流程图。

## 概念讲解手册（learning）

一份由浅入深的单文件讲解：答案、职责框架、逐步流程、完整例子、术语、实际工作。
适合“我想了解登录这块”这种要建立整体认识、而不是追一条计算路径的请求。

- 写法与 manifest：[learning.md](learning.md)
- 样例：`assets/learning.example.json`
- 构建：`python scripts/build_knowledge.py knowledge.json NEW_OUTPUT`
- 校验：`python scripts/verify_handbook.py NEW_OUTPUT` 和 `NEW_OUTPUT/handbook.html`
- 旧的 knowledge manifest 字段：[knowledge.md](knowledge.md)

## 多页文档站点（book.json）

旧版的多页 HTML 站点，左侧导航、正文、右侧问答。问答通过 `chat_server.py` 调
OpenAI 兼容接口，需要用户自己的 API Key，和流程图的 Codex 追问是两套独立实现。

- 页面写法：[authoring.md](authoring.md)
- 盘点与事实核对：[audit-checklist.md](audit-checklist.md)
- 构建与校验：[validation.md](validation.md)
- 问答面板与 relay：[chat.md](chat.md)
- 脚本：`init_handbook.py`、`import_project.py`、`build_handbook.py`、
  `verify_handbook.py`、`chat_server.py`

这两种格式不使用 `flow.json`、`flow_server.py` 或页面内的 Codex 追问。
