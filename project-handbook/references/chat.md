# 手册问答面板

## 设计目标

生成的页面在桌面端采用“左侧导航—中间正文—右侧问答”的三栏工作区；窄屏
自动改为正文在上、问答在下。问答只把检索到的手册片段交给模型，并要求回答
使用 `[1]`、`[2]` 标注来源，证据不足时明确拒答。

## 推荐运行方式：本地 relay

图解模式默认在浏览器本地返回证据摘录，不调用模型。安全预览可运行
`python project-handbook/scripts/chat_server.py .\my-handbook --evidence-only`，
该模式不读取环境变量中的 API Key，也不会使用服务端预设凭据调用模型。
用户仍可在页面显式选择模型问答、填写供应商地址和 API Key，获取并选择模型后发送；
这会将问题及检索片段发送给所选供应商，并非严格禁止网络的运行模式。
发送模型问答时页面会自动带上资料发送确认，不单独展示勾选框。relay 的模型请求要求 `consent: true`；
`selected_node` 仅接受索引中已有的 URL。获取模型会请求 OpenAI-compatible
的 `/v1/models`；本地 relay 提供同源 `/api/models` 代理。

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
相对地址无法解析；请改用 relay 输出的 localhost 地址。relay 只接受同源浏览器
请求，从 file:// 填写完整 relay URL 也会被拒绝。本地证据检索不受此限制。

## 浏览器直连（仅用于兼容性测试）

右侧连接设置填写接口 URL 和 API Key 后，点击「获取模型」拉取上游模型列表。
在本地服务页面中，供应商地址也通过同源 relay 转发；接口地址留空则使用
本地 relay 的环境变量配置。仅 `file://` 页面尝试浏览器直连。
双击 `site/index.html` 时浏览器可能拦截跨域 `/v1/models`，失败信息
显示在「获取模型」下方；请改用 localhost relay。密钥只保存在当前页面内存，
不写入 `sessionStorage` 或生成文件。

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

`endpoint` 默认是浏览器请求的 relay 地址 `/api/chat`，地址栏留空时使用它。
若在右侧填写供应商 `http(s)` 地址，本地服务页面通过 `/api/chat` 和 `/api/models`
转发请求；仅直接打开文件时尝试供应商直连。`model` 留空时必须先获取模型列表再选择；relay 仍可用
`--model` 或 `OPENAI_MODEL` 作为服务端回退值。

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
