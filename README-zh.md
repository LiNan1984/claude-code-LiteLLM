# Claude Code + LiteLLM 代理方案

通过 LiteLLM 代理，让 Claude Code 调用任何 OpenAI 兼容 API（如 glm-5-fp8）。

## 架构

```
Claude Code → LiteLLM Proxy (localhost:4000) → OpenAI 兼容 API (如 finmall.com)
```

Claude Code 发送 Anthropic 格式请求 → LiteLLM 翻译为 OpenAI Chat Completions 格式 → 转发到上游 API。

## 前提条件

- macOS / Linux
- [uv](https://docs.astral.sh/uv/) 已安装（`brew install uv`）
- Claude Code 已安装（`npm install -g @anthropic-ai/claude-code`）
- 你的 API 地址和密钥

## 快速部署（5 步）

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/claude-code-LiteLLM.git
cd claude-code-LiteLLM
```

### 2. 创建 Python 3.11 环境

```bash
uv init --python 3.11
uv python install 3.11
uv python pin 3.11
uv venv --python 3.11
```

### 3. 安装 LiteLLM

```bash
uv pip install 'litellm[proxy]' -i https://mirrors.aliyun.com/pypi/simple/
```

验证：

```bash
.venv/bin/python --version   # Python 3.11.x
.venv/bin/litellm --version  # 显示版本号
```

> **注意：Python 必须 >= 3.10**。Python 3.9 会导致 `|` 类型语法报错。

### 4. 创建 LiteLLM 配置

```bash
cp litellm-config/config.yaml.example litellm-config/config.yaml
```

编辑 `litellm-config/config.yaml`，填入你的 API 信息：

```yaml
model_list:
  - model_name: glm-5-fp8                    # Claude Code 显示的模型名
    litellm_params:
      model: openai/glm-5-fp8                 # openai/ 前缀 = OpenAI 兼容 API
      api_base: "https://your-api.com/v1"     # 你的 API 地址（到 /v1）
      api_key: "your-api-key-here"            # 你的 API 密钥
      timeout: 300
      drop_params: true                        # 丢弃上游不支持的参数

litellm_settings:
  drop_params: true
  master_key: "sk-litellm-master-your-secret"  # 自定义一个代理密钥
  # 关键：强制使用 chat/completions 格式，不用 Responses API
  use_chat_completions_url_for_anthropic_messages: true
```

**配置说明：**

| 字段 | 说明 |
|------|------|
| `model_name` | Claude Code 使用的模型名，可自定义 |
| `model` | `openai/` 前缀表示 OpenAI 兼容格式，后面是实际模型名 |
| `api_base` | API 基础地址，到 `/v1`，不要带 `/chat/completions` |
| `drop_params` | 必须为 true，Claude Code 会发送很多上游不支持的参数 |
| `master_key` | 代理认证密钥，自定义一个即可 |
| `use_chat_completions_url_for_anthropic_messages` | **必须为 true**，否则上游 API 会报 `input should be a valid string` 错误 |

### 5. 创建 Claude Code 项目配置

```bash
cp .claude/settings.json.example .claude/settings.json
```

编辑 `.claude/settings.json`，填入对应值：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:4000",
    "ANTHROPIC_AUTH_TOKEN": "sk-litellm-master-your-secret",
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_MODEL": "glm-5-fp8",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5-fp8",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5-fp8",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5-fp8",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "MAX_THINKING_TOKENS": "10000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"
  },
  "model": "glm-5-fp8"
}
```

**要点：**

- `ANTHROPIC_AUTH_TOKEN` 必须匹配 `config.yaml` 中的 `master_key`
- `ANTHROPIC_API_KEY` 设为空，避免与 AUTH_TOKEN 冲突
- `ANTHROPIC_MODEL` 必须匹配 `config.yaml` 中的 `model_name`

## 使用方法

### 启动 LiteLLM 代理

终端 1：

```bash
cd ~/claude-code-LiteLLM
.venv/bin/litellm --config litellm-config/config.yaml --port 4000
```

看到 `Uvicorn running on http://0.0.0.0:4000` 表示启动成功。

### 启动 Claude Code

终端 2：

```bash
cd ~/claude-code-LiteLLM
claude
```

项目级 `.claude/settings.json` 会自动生效，Claude Code 将通过 LiteLLM 代理调用你的模型。

### 验证连接

```bash
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-litellm-master-your-secret" \
  -d '{
    "model": "glm-5-fp8",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 50
  }'
```

返回正常 JSON 响应说明代理工作正常。

## 与系统 Claude Code 共存

项目级 `.claude/settings.json` 只在项目目录下生效，不影响其他地方的 Claude Code：

| 启动目录 | 行为 |
|---------|------|
| `cd ~/claude-code-LiteLLM && claude` | 走 LiteLLM 代理 |
| 其他目录 `claude` | 走系统默认配置 |

## 项目结构

```
claude-code-LiteLLM/
├── .claude/
│   └── settings.json           # Claude Code 项目配置（含代理地址）
├── .python-version             # Python 3.11 pin
├── litellm-config/
│   ├── config.yaml             # LiteLLM 代理配置（含 API 密钥，不提交到 Git）
│   ├── config.yaml.example     # 配置模板
│   ├── start-litellm.sh        # 启动代理脚本
│   └── set-env.sh              # 环境变量设置脚本
├── pyproject.toml              # uv 项目配置
├── .gitignore
└── README-zh.md
```

## 常见问题

### 1. `unsupported operand type(s) for |: '_TypedDictMeta'`

Python 版本太低（< 3.10）。解决方案：使用 Python 3.11+。

### 2. `No connected db`

移除 `config.yaml` 中的 `master_key` 和 `database_url`，或者将 `master_key` 放到 `litellm_settings` 中（不是 `general_settings`）。

### 3. `Input should be a valid string` / `178 validation errors`

LiteLLM 使用了 Responses API 格式而非 Chat Completions。解决方案：确保 `config.yaml` 中有：

```yaml
litellm_settings:
  use_chat_completions_url_for_anthropic_messages: true
```

### 4. `Auth conflict: Both a token and an API key are set`

`ANTHROPIC_AUTH_TOKEN` 和 `ANTHROPIC_API_KEY` 同时存在。解决方案：在 `.claude/settings.json` 中将 `ANTHROPIC_API_KEY` 设为空字符串。

### 5. 端口 4000 被占用

修改启动命令中的 `--port` 参数，同时修改 `.claude/settings.json` 中的 `ANTHROPIC_BASE_URL`。

### 6. 模型返回空内容

`max_tokens` 设置太小。建议 >= 4096。

## 可选：开机自启动（macOS launchd）

创建 `~/Library/LaunchAgents/com.litellm.proxy.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.litellm.proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/你的用户名/claude-code-LiteLLM/.venv/bin/litellm</string>
        <string>--config</string>
        <string>/Users/你的用户名/claude-code-LiteLLM/litellm-config/config.yaml</string>
        <string>--port</string>
        <string>4000</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/litellm.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/litellm-error.log</string>
</dict>
</plist>
```

加载：

```bash
launchctl load ~/Library/LaunchAgents/com.litellm.proxy.plist
```

卸载：

```bash
launchctl unload ~/Library/LaunchAgents/com.litellm.proxy.plist
```

## 技术要点

1. **Python >= 3.10**：LiteLLM 使用了 PEP 604 联合类型语法（`X | Y`），低版本 Python 会报错
2. **`drop_params: true`**：Claude Code 发送大量 Anthropic 特有参数，上游 API 通常不支持，必须丢弃
3. **`use_chat_completions_url_for_anthropic_messages: true`**：强制 LiteLLM 将 Anthropic Messages API 翻译为 OpenAI Chat Completions 格式，而不是 Responses API 格式
4. **项目级 settings.json**：`~/.claude/settings.json`（全局）的优先级高于 shell 环境变量，所以必须用项目级 `.claude/settings.json` 来覆盖
5. **`ANTHROPIC_AUTH_TOKEN` 而非 `ANTHROPIC_API_KEY`**：LiteLLM 使用 master_key 认证，需要用 AUTH_TOKEN 匹配

## 许可证

MIT
