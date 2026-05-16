#!/usr/bin/env bash
set -e

echo "=== LightingAgent 安装脚本 ==="
echo ""
echo "⚠️  前置手动步骤（脚本无法自动完成）："
echo "    DWG 文件转换需要 ODA File Converter，请先手动安装："
echo "    https://www.opendesign.com/guestfiles/oda_file_converter"
echo "    安装后确认路径：/Applications/ODAFileConverter.app"
echo ""
read -p "已安装 ODA File Converter？按 Enter 继续，Ctrl+C 退出先去安装..." _

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
    echo "  [警告] Radiance 工具 '$cmd' 未找到，请检查 PATH"
  fi
done

# 4. 安装 Python 依赖
echo "[2/3] 安装 Python 依赖..."
pip install -e .

# 5. 验证安装
echo "[3/3] 验证安装..."
python -c "from lighting_agent import schemas; print('  Python 包: OK')"
echo "  Radiance oconv:       $(command -v oconv || echo '❌ 未找到')"

ODA_BIN="/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
if [ -f "$ODA_BIN" ]; then
  echo "  ODA File Converter:   ✅ 已安装"
else
  echo "  ODA File Converter:   ❌ 未找到，DWG 输入将不可用"
  echo "     → 请安装：https://www.opendesign.com/guestfiles/oda_file_converter"
fi

# LibreDWG 作为备用（可选）
if command -v dwg2dxf &>/dev/null; then
  echo "  LibreDWG dwg2dxf:     ✅ 已安装（备用）"
else
  echo "  LibreDWG dwg2dxf:     — 未安装（ODA 已安装则无需此项）"
fi

echo ""
echo "=== 安装完成 ==="
echo "使用方法："
echo "  lighting-agent run --cad plan.dwg --ies ./ies/ --output ./output/"
echo "  lighting-agent run --cad plan.dxf --ies ./ies/ --output ./output/"
echo "  python -m mcp_server.server  # 启动 MCP Server"
