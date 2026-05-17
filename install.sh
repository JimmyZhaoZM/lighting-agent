#!/usr/bin/env bash
set -e

echo "=== LightingAgent 安装脚本 ==="
echo ""
echo "⚠️  以下两项需要手动安装（脚本无法自动完成）："
echo ""
echo "  1. Radiance（照度仿真引擎，必须）"
echo "     Homebrew formula 已下架，请从官方 GitHub Releases 手动安装 pkg："
echo "     https://github.com/LBNL-ETA/Radiance/releases"
echo "     Apple Silicon (M1/M2/M3/M4)：下载 Radiance_*_OSX_arm64.pkg"
echo "     Intel Mac：                  下载 Radiance_*_OSX.pkg"
echo "     安装后将 /usr/local/radiance/bin 加入 PATH，确认 'which oconv' 有输出"
echo ""
echo "  2. ODA File Converter（仅 DWG 输入需要）"
echo "     https://www.opendesign.com/guestfiles/oda_file_converter"
echo "     安装后确认路径：/Applications/ODAFileConverter.app"
echo ""
read -p "已完成上述手动安装？按 Enter 继续，Ctrl+C 退出先去安装..." _

# 1. 检查 Homebrew
if ! command -v brew &>/dev/null; then
  echo "[错误] 未找到 Homebrew，请先安装：https://brew.sh"
  exit 1
fi

# 2. 安装 Python 依赖
echo "[1/2] 安装 Python 依赖..."
pip install -e .

# 3. 验证安装
echo "[2/2] 验证安装..."
python -c "from lighting_agent import schemas; print('  Python 包: OK')"

echo ""
if command -v oconv &>/dev/null; then
  echo "  Radiance oconv:       ✅ $(which oconv)"
else
  echo "  Radiance oconv:       ❌ 未找到 — 仿真功能不可用"
  echo "     → 请从 https://github.com/NREL/Radiance/releases 安装后重新运行"
fi

ODA_BIN="/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
if [ -f "$ODA_BIN" ]; then
  echo "  ODA File Converter:   ✅ 已安装"
else
  echo "  ODA File Converter:   ❌ 未找到 — DWG 输入将不可用"
  echo "     → 请安装：https://www.opendesign.com/guestfiles/oda_file_converter"
fi

if command -v dwg2dxf &>/dev/null; then
  echo "  LibreDWG dwg2dxf:     ✅ 已安装（ODA 备用）"
else
  echo "  LibreDWG dwg2dxf:     — 未安装（ODA 已安装则无需）"
fi

echo ""
echo "=== 安装完成 ==="
echo "使用方法："
echo "  lighting-agent run --cad plan.dwg --ies ./ies/ --output ./output/"
echo "  lighting-agent run --cad plan.dxf --ies ./ies/ --output ./output/"
echo "  python -m mcp_server.server  # 启动 MCP Server"
