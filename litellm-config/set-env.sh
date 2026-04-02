#!/bin/bash
# 环境变量配置（仅在无法使用项目级 .claude/settings.json 时使用）
# 使用方法: source set-env.sh

unset ANTHROPIC_AUTH_TOKEN
unset ANTHROPIC_API_KEY

export ANTHROPIC_BASE_URL="http://localhost:4000"
export ANTHROPIC_AUTH_TOKEN="sk-litellm-master-your-secret"
export ANTHROPIC_MODEL="glm-5-fp8"

echo "Environment variables set:"
echo "  ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL"
echo "  ANTHROPIC_MODEL=$ANTHROPIC_MODEL"
echo ""
echo "Now run: claude"
