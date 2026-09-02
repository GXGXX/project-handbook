# 手册问答面板

## 设计目标

生成的页面在桌面端采用“左侧导航—中间正文—右侧问答”的三栏工作区；窄屏
自动改为正文在上、问答在下。问答只把检索到的手册片段交给模型，并要求回答
使用 `[1]`、`[2]` 标注来源，证据不足时明确拒答。

## 推荐运行方式：本地 relay

不要把 API Key 写入 `book.json`、`content/`、`site/` 或 Git。构建时会拒绝
包含 `api_key`、`token`、`secret`、`password` 等字段的 chat 配置。

在 PowerShell 中：

```powershell
$env:OPENAI_API_KEY = "粘贴你的密钥"
$env:OPENAI_MODEL = "gpt-4o-mini"
python project-handbook/scripts/chat_server.py .\my-handbook
```

然后打开命令行输出的 `http://127.0.0.1:8765/`。relay 会读取
`site/assets/search-index.json`，进行轻量关键词检索，再调用 OpenAI-compatible
的 `/chat/completions` 接口。可用 `--base-url` 切换到兼容服务，例如本地模型：

```powershell
python project-handbook/scripts/chat_server.py .\my-handbook `
  --base-url http://127.0.0.1:11434/v1 --model llama3.1
```

`--base-url` 也可以直接传完整的 `/chat/completions` 地址。服务默认只绑定
`127.0.0.1`，避免把带密钥的 relay 暴露到局域网。

如果直接双击 `site/index.html`，浏览器地址是 `file://`，默认的 `/api/chat`
相对地址无法解析；面板会提示这一点。请改用 relay 输出的 localhost 地址，或在
连接设置中填入完整的 `http://127.0.0.1:8765/api/chat`。

## 浏览器直连（仅用于兼容性测试）

右侧“连接设置”可切换到“浏览器直连”，填写接口地址、模型和 API Key。密钥
只保存在当前页面内存，不写入 `sessionStorage` 或生成文件；但浏览器网络记录、
扩展和接口 CORS 策略仍可能暴露风险，因此不建议作为生产部署方式。

## 配置项

`book.json` 可包含以下非敏感配置：

```json
{
  "chat": {
    "enabled": true,
    "mode": "relay",
    "endpoint": "/api/chat",
    "model": "",
    "context_chars": 16000,
    "max_history": 8,
    "title": "手册问答",
    "placeholder": "输入问题，答案将附带来源…"
  }
}
```

`endpoint` 是浏览器请求地址，不是模型供应商地址；供应商地址通过 relay 的
`--base-url` 或 `OPENAI_BASE_URL` 设置。`model` 留空时从右侧输入框、
`--model` 或 `OPENAI_MODEL` 中取得。

### 关于“默认消耗 agent token”

静态 HTML 与 Codex/Claude 等 agent 的当前会话隔离，不能自动继承宿主会话的 token
或登录态。本版本把 `/api/chat` 设计成可替换的 relay 接口：默认使用本地进程读取
环境变量密钥；如果你的 agent 宿主提供了受控的模型代理，只需把 `chat.endpoint`
指向该代理，并让代理负责认证和限流，不要把 agent token 写进页面。

## 已知边界

- 检索是可解释的关键词基线，不是向量数据库；大型仓库应替换为真正的混合检索。
- 静态 verifier 能检查面板、资产和配置，不能证明模型回答事实正确；应保留一组
  人工问答回归样例。
- 需要真实浏览器烟测：打开页面、切换主题、询问一个有明确来源的问题，并确认
  答案下方的来源链接能跳回对应章节。
