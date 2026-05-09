# 新电脑 Claude Code + 自定义大模型 配置指南

从零开始配置 Claude Code 使用自定义大模型（如智谱 GLM、LiteLLM 代理等）。

---

## 目录

1. [安装 Homebrew](#1-安装-homebrew)
2. [安装 nvm 和 Node.js](#2-安装-nvm-和-nodejs)
3. [安装 Claude Code](#3-安装-claude-code)
4. [安装 uv 和 Python 环境](#4-安装-uv-和-python-环境)
5. [配置 LiteLLM 代理](#5-配置-litellm-代理)
6. [配置 Claude Code 使用自定义模型](#6-配置-claude-code-使用自定义模型)
7. [日常使用](#7-日常使用)
8. [常见问题](#8-常见问题)

---

## 1. 安装 Homebrew

macOS 必装包管理器。

```bash
# 安装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 添加到 PATH（Apple Silicon Mac）
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# 验证
brew --version
```

### 配置国内镜像（可选，加速下载）

```bash
# 设置 Homebrew 镜像
export HOMEBREW_BREW_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git"
export HOMEBREW_CORE_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git"
export HOMEBREW_BOTTLE_DOMAIN="https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles"

# 写入配置文件
echo 'export HOMEBREW_BREW_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git"' >> ~/.zprofile
echo 'export HOMEBREW_CORE_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git"' >> ~/.zprofile
echo 'export HOMEBREW_BOTTLE_DOMAIN="https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles"' >> ~/.zprofile
```

---

## 2. 安装 nvm 和 Node.js

### 安装 nvm

```bash
# 安装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# 重新加载 shell
source ~/.zshrc

# 验证
nvm --version
```

### 配置 nvm 镜像（国内加速）

```bash
# 设置 Node.js 镜像
export NVM_NODEJS_ORG_MIRROR="https://npmmirror.com/mirrors/node"
echo 'export NVM_NODEJS_ORG_MIRROR="https://npmmirror.com/mirrors/node"' >> ~/.zshrc
```

### 安装 Node.js

```bash
# 安装最新 LTS 版本
nvm install --lts

# 或安装指定版本
nvm install 22

# 设置默认版本
nvm alias default 22

# 验证
node --version   # v22.x.x
npm --version    # 10.x.x
```

---

## 3. 安装 Claude Code

```bash
# 全局安装 Claude Code
npm install -g @anthropic-ai/claude-code

# 验证
claude --version

# 首次运行（会引导登录 Anthropic 账号）
claude
```

### 配置 npm 镜像（可选）

```bash
# 设置 npm 镜像
npm config set registry https://registry.npmmirror.com

# 或使用 pnpm（更快）
npm install -g pnpm
pnpm config set registry https://registry.npmmirror.com
```

---

## 4. 安装 uv 和 Python 环境

uv 是新一代 Python 包管理器，比 pip 快 10-100 倍。

### 安装 uv

```bash
# macOS/Linux
brew install uv

# 或使用 curl
curl -LsSf https://astral.sh/uv/install.sh | sh

# 验证
uv --version
```

### 创建项目目录和 Python 环境

```bash
# 创建项目目录
mkdir -p ~/claude-code-LiteLLM
cd ~/claude-code-LiteLLM

# 初始化项目（指定 Python 3.11+）
uv init --python 3.11
uv python install 3.11
uv python pin 3.11

# 创建虚拟环境
uv venv --python 3.11

# 验证
.venv/bin/python --version   # Python 3.11.x
```

---

## 5. 配置 LiteLLM 代理

LiteLLM 是一个统一的 LLM 代理，可以将 Anthropic 格式转换为 OpenAI 兼容格式。

### 安装 LiteLLM

```bash
cd ~/claude-code-LiteLLM

# 安装 LiteLLM（带代理功能）
uv pip install 'litellm[proxy]' -i https://mirrors.aliyun.com/pypi/simple/

# 验证
.venv/bin/litellm --version
```

### 创建配置文件

```bash
# 创建配置目录
mkdir -p litellm-config

# 创建配置文件
cat > litellm-config/config.yaml << 'EOF'
model_list:
  # 示例：OpenAI 兼容 API
  - model_name: glm-5-fp8
    litellm_params:
      model: openai/glm-5-fp8
      api_base: "https://your-api.com/v1"
      api_key: "your-api-key-here"
      timeout: 300

litellm_settings:
  # 过滤后端不支持的参数
  drop_params: true
  master_key: "sk-litellm-master-your-secret"
  # 关键：使用 chat/completions 格式
  use_chat_completions_url_for_anthropic_messages: true
  # 禁用 SSL 验证（某些 API 需要）
  ssl_verify: false
EOF
```

### 创建启动脚本

```bash
cat > litellm-config/start-litellm.sh << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LITELLM_BIN="$PROJECT_DIR/.venv/bin/litellm"
CONFIG="$SCRIPT_DIR/config.yaml"
PORT=4000

echo "Starting LiteLLM proxy on port $PORT..."
$LITELLM_BIN --config "$CONFIG" --port $PORT
EOF

chmod +x litellm-config/start-litellm.sh
```

### 启动 LiteLLM

```bash
cd ~/claude-code-LiteLLM
./litellm-config/start-litellm.sh

# 或直接运行
.venv/bin/litellm --config litellm-config/config.yaml --port 4000
```

看到 `Uvicorn running on http://0.0.0.0:4000` 表示启动成功。

---

## 6. 配置 Claude Code 使用自定义模型

有两种方式：**直连 API** 和 **LiteLLM 代理**。

### 方式一：直连智谱 GLM API（推荐）

直接使用智谱的 Anthropic 兼容 API，无需 LiteLLM 代理。

```bash
# 编辑全局配置
mkdir -p ~/.claude
cat > ~/.claude/settings.json << 'EOF'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "env": {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.5-air",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-4.7",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5",
    "ANTHROPIC_AUTH_TOKEN": "your-zhipu-api-token-here",
    "ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "MAX_THINKING_TOKENS": "10000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"
  },
  "model": "opus[1m]"
}
EOF
```

### 方式二：通过 LiteLLM 代理

适合使用第三方 OpenAI 兼容 API。

```bash
# 编辑全局配置
cat > ~/.claude/settings.json << 'EOF'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:4000",
    "ANTHROPIC_AUTH_TOKEN": "sk-litellm-master-your-secret",
    "ANTHROPIC_API_KEY": "",
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
EOF
```

**关键配置说明：**

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_BASE_URL` | API 地址（直连用智谱地址，代理用 `http://localhost:4000`）|
| `ANTHROPIC_AUTH_TOKEN` | API 密钥（直连用智谱 Token，代理用 LiteLLM master_key）|
| `ANTHROPIC_API_KEY` | 设为空，避免与 AUTH_TOKEN 冲突 |
| `model` | 默认模型名，加 `[1m]` 后缀启用扩展思考 |

---

## 7. 日常使用

### 启动流程

```bash
# 方式一：直连智谱（无需启动代理）
claude

# 方式二：使用 LiteLLM 代理
# 终端 1：启动代理
cd ~/claude-code-LiteLLM && ./litellm-config/start-litellm.sh

# 终端 2：启动 Claude Code
claude
```

### 验证连接

```bash
# 测试 LiteLLM 代理
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-litellm-master-your-secret" \
  -d '{
    "model": "glm-5-fp8",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 50
  }'

# 测试智谱直连
curl -X POST https://open.bigmodel.cn/api/anthropic/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-zhipu-api-token" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "glm-5",
    "max_tokens": 50,
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 开机自启动 LiteLLM（macOS）

```bash
cat > ~/Library/LaunchAgents/com.litellm.proxy.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.litellm.proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/$(whoami)/claude-code-LiteLLM/.venv/bin/litellm</string>
        <string>--config</string>
        <string>/Users/$(whoami)/claude-code-LiteLLM/litellm-config/config.yaml</string>
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
EOF

# 加载
launchctl load ~/Library/LaunchAgents/com.litellm.proxy.plist

# 卸载
# launchctl unload ~/Library/LaunchAgents/com.litellm.proxy.plist
```

---

## 8. 常见问题

### Python 版本错误

```
unsupported operand type(s) for |: '_TypedDictMeta'
```

**原因**：Python < 3.10

**解决**：使用 Python 3.11+

```bash
uv python install 3.11
uv venv --python 3.11
```

### Auth conflict

```
Auth conflict: Both a token and an API key are set
```

**解决**：在 `settings.json` 中将 `ANTHROPIC_API_KEY` 设为空字符串。

### Input should be a valid string

```
178 validation errors for MessagesRequest
```

**原因**：LiteLLM 使用了错误的 API 格式

**解决**：确保 `config.yaml` 中有：

```yaml
litellm_settings:
  use_chat_completions_url_for_anthropic_messages: true
```

### 端口被占用

```bash
# 查看端口占用
lsof -i :4000

# 杀掉进程
kill -9 <PID>
```

### 模型返回空内容

**原因**：`max_tokens` 太小

**解决**：设置 `max_tokens >= 4096`

---

## 快速命令参考

```bash
# === 安装 ===
# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# Node.js
nvm install 22 && nvm alias default 22

# Claude Code
npm install -g @anthropic-ai/claude-code

# uv
brew install uv

# LiteLLM
cd ~/claude-code-LiteLLM && uv pip install 'litellm[proxy]'

# === 启动 ===
# LiteLLM 代理
cd ~/claude-code-LiteLLM && .venv/bin/litellm --config litellm-config/config.yaml --port 4000

# Claude Code
claude

# === 验证 ===
node --version && npm --version && claude --version
uv --version && .venv/bin/litellm --version
```

---

## 项目结构

```
~/claude-code-LiteLLM/
├── .venv/                      # Python 虚拟环境
├── litellm-config/
│   ├── config.yaml             # LiteLLM 配置（含 API 密钥）
│   └── start-litellm.sh        # 启动脚本
├── pyproject.toml              # uv 项目配置
└── .python-version             # Python 版本锁定

~/.claude/
├── settings.json               # Claude Code 全局配置
├── agents/                     # 自定义 Agent
├── rules/                      # 自定义规则
└── skills/                     # 自定义技能
```
