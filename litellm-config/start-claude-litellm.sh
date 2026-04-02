#!/bin/bash
# Claude Code + LiteLLM 一键启动
# 使用方法: ./start-claude-litellm.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LITELLM_BIN="$PROJECT_DIR/.venv/bin/litellm"
CONFIG="$SCRIPT_DIR/config.yaml"
PORT=4000

# 检查配置文件
if [ ! -f "$CONFIG" ]; then
    echo "Error: config.yaml not found."
    echo "Run: cp $SCRIPT_DIR/config.yaml.example $SCRIPT_DIR/config.yaml"
    exit 1
fi

# 检查 LiteLLM 代理是否已运行
if ! lsof -i:$PORT > /dev/null 2>&1; then
    echo "Starting LiteLLM proxy..."
    $LITELLM_BIN --config "$CONFIG" --port $PORT &
    sleep 5
    echo "LiteLLM proxy started on port $PORT"
else
    echo "LiteLLM proxy already running on port $PORT"
fi

echo ""
echo "Starting Claude Code..."
echo "Working directory: $PROJECT_DIR"
echo ""

cd "$PROJECT_DIR"
claude
