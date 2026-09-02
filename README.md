# Project Handbook

把代码库和文档整理成一套可核验、可离线打开的项目手册，并提供一个可选的
“左侧导航—中间正文—右侧问答”工作区。它受到
[`aicoding-cookbook`](https://github.com/lili-luo/aicoding-cookbook) 中
`docs-to-book` 思路启发，但脚本和模板在此仓库中独立实现，避免把原仓库
的隐含假设直接带进新的项目。

## 为什么做这个版本

原方案的阅读体验和方法论很有价值，但真实落地时容易遇到几类问题：

- 配置、slug、页面缺失没有统一 schema；部分错误会在生成占位页后仍以成功结束。
- Node CommonJS/ESM、Mermaid 版本、浏览器验证依赖环境，跨平台复现成本高。
- 生成器把标题和摘要直接拼进 HTML，内容页也缺少安全边界。
- `verify.js` 偏结构正则，不能稳定解析相对链接、重复锚点或残留旧页面。
- 搜索索引截断正文，事实核对主要依赖人工抽查。
- 生成后的静态页面只能阅读，缺少基于手册证据的交互式追问入口。

这个版本的取舍是：用 Python 标准库完成初始化、构建和验证；默认严格失败；
把证据清单作为可选的一等输入；把浏览器烟测明确列为静态校验之外的步骤。
本轮迭代增加了轻量关键词检索和本地 relay：页面只发送问题与会话，relay 从
`search-index.json` 取上下文、要求模型引用 `[1]` 来源，并把 API Key 留在进程
环境变量中。

## 快速开始

```text
python project-handbook/scripts/init_handbook.py ./my-handbook
python project-handbook/scripts/build_handbook.py ./my-handbook
python project-handbook/scripts/verify_handbook.py ./my-handbook
```

如果代码和文档是两个目录，可以直接导入一轮素材（只读扫描源目录，并只写入
新输出目录）：

```powershell
python project-handbook/scripts/import_project.py `
  --client D:\path\to\client `
  --docs D:\path\to\docs `
  --output .\my-handbook
```

导入器默认抽样脚本/文本、Excel 工作簿元数据和文件类型统计；不会复制原始工作簿，
也会对明显的密钥格式做脱敏。大项目可用 `--sample-files` 和
`--max-excerpt-bytes` 控制输出规模。

编辑 `my-handbook/book.json` 和 `my-handbook/content/*.html`。构建结果位于
`my-handbook/site/`，直接打开 `site/index.html` 即可；搜索索引会内嵌到页面，
不依赖 `file://` 下的 `fetch()`。桌面端会同时显示右侧问答面板。要实际询问模型，
推荐启动本地 relay（不要把密钥写进配置或 HTML）：

```powershell
$env:OPENAI_API_KEY = "粘贴你的密钥"
$env:OPENAI_MODEL = "gpt-4o-mini"
python project-handbook/scripts/chat_server.py .\my-handbook
```

然后打开终端输出的 `http://127.0.0.1:8765/`。兼容 OpenAI API 的本地或云端服务
可通过 `--base-url` 切换。完整配置、CORS 和安全边界见
[references/chat.md](project-handbook/references/chat.md)。需要 Mermaid 时，放入
经过固定版本确认的 `assets/mermaid.min.js`；否则优先使用本地 SVG。

注意：静态 HTML 无法自动继承 Codex 当前会话的 token；如果希望费用和权限由 agent
统一管理，应让 agent 宿主提供一个受控的 `/api/chat` relay，再把 `chat.endpoint`
指向它。

## 目录

```text
project-handbook/
├── SKILL.md
├── agents/openai.yaml
├── scripts/
│   ├── init_handbook.py
│   ├── import_project.py
│   ├── build_handbook.py
│   ├── verify_handbook.py
│   └── chat_server.py
├── references/
│   ├── audit-checklist.md
│   ├── authoring.md
│   ├── validation.md
│   └── chat.md
└── assets/
    ├── book.example.json
    ├── style.css
    ├── app.js
    └── chat.js
```

## 设计边界

静态 verifier 能证明结构、链接、资产、锚点和证据 token 的一致性，不能证明
一条业务陈述真的正确，也不能替代真实浏览器渲染。交付记录应同时写明源码
核对范围和浏览器烟测结果。

## 作品集叙事

这个项目可以按“观察—假设—实验—证据”来展示：先指出原方案在严格失败、
`file://` 搜索、HTML 安全和事实核验上的落差；再说明为什么选择标准库、
预检构建、facts manifest 和本地 relay；最后用回归测试、跨 Python 版本 CI、
来源可点击的问答面板和可重打包的 zip 证明改动不是只停留在 prompt 层面。

本机真实素材演练的脱敏记录见 [TEST_REPORT.md](TEST_REPORT.md)；真实游戏文件只
留在临时目录，没有进入本仓库。

## 许可证与致谢

本项目是独立实现的个人作品集项目。原始灵感来自上面的公开仓库；原仓库
当前没有在根目录提供通用许可证，因此本项目不复制其实现代码，并保留来源
链接以便读者比较设计取舍。
