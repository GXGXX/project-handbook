# Project Handbook

把代码库和文档整理成一套可核验、可离线打开的项目手册。它受到
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

这个版本的取舍是：用 Python 标准库完成初始化、构建和验证；默认严格失败；
把证据清单作为可选的一等输入；把浏览器烟测明确列为静态校验之外的步骤。

## 快速开始

```text
python project-handbook/scripts/init_handbook.py ./my-handbook
python project-handbook/scripts/build_handbook.py ./my-handbook
python project-handbook/scripts/verify_handbook.py ./my-handbook
```

编辑 `my-handbook/book.json` 和 `my-handbook/content/*.html`。构建结果位于
`my-handbook/site/`，直接打开 `site/index.html` 即可；搜索索引会内嵌到页面，
不依赖 `file://` 下的 `fetch()`。需要 Mermaid 时，放入
经过固定版本确认的 `assets/mermaid.min.js`；否则优先使用本地 SVG。

## 目录

```text
project-handbook/
├── SKILL.md
├── agents/openai.yaml
├── scripts/
│   ├── init_handbook.py
│   ├── build_handbook.py
│   └── verify_handbook.py
├── references/
│   ├── audit-checklist.md
│   ├── authoring.md
│   └── validation.md
└── assets/
    ├── book.example.json
    ├── style.css
    └── app.js
```

## 设计边界

静态 verifier 能证明结构、链接、资产、锚点和证据 token 的一致性，不能证明
一条业务陈述真的正确，也不能替代真实浏览器渲染。交付记录应同时写明源码
核对范围和浏览器烟测结果。

## 作品集叙事

这个项目可以按“观察—假设—实验—证据”来展示：先指出原方案在严格失败、
`file://` 搜索、HTML 安全和事实核验上的落差；再说明为什么选择标准库、
预检构建和 facts manifest；最后用 5 个回归测试、跨 Python 版本 CI 和可重打包
的 zip 证明改动不是只停留在 prompt 层面。

## 许可证与致谢

本项目是独立实现的个人作品集项目。原始灵感来自上面的公开仓库；原仓库
当前没有在根目录提供通用许可证，因此本项目不复制其实现代码，并保留来源
链接以便读者比较设计取舍。
