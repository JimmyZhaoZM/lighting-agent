#!/usr/bin/env bash
set -e

echo "=== LightingAgent 安装脚本 ==="

# 1. 检查 Homebrew
if ! command -v brew &>/dev/null; then
  echo "[错误] 未找到 Homebrew，请先安装：https://brew.sh"
  exit 1
fi

# 2. 安装 Radiance
if ! command -v oconv &>/dev/null; then
  echo "[1/3] 安装 Radiance..."
  brew install radiance
else
  echo "[1/3] Radiance 已安装：$(which oconv)"
fi

# 3. 验证 Radiance 工具
for cmd in oconv rtrace rpict falsecolor ies2rad; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "[警告] Radiance 工具 '$cmd' 未找到，请检查 PATH"
  fi
done

# 4. 安装 Python 依赖
echo "[2/3] 安装 Python 依赖..."
pip install -e .

# 5. 验证安装
echo "[3/3] 验证安装..."
python -c "from lighting_agent import schemas; print('  Python 包: OK')"
echo "  Radiance: $(oconv -r 2>&1 | head -1 || echo 'OK')"

echo ""
echo "=== 安装完成 ==="
echo "使用方法："
echo "  lighting-agent run --dxf plan.dxf --ies ./ies/ --output ./output/"
echo "  python -m mcp_server.server  # 启动 MCP Server"
