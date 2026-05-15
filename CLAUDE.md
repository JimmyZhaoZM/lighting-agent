# LightingAgent — Claude Code 项目指南

## 项目目标
AI 驱动的照度计算与布灯设计系统。输入 CAD 图纸 + IES 文件 + 照度要求，输出优化的布灯方案、PDF 报告和标注 CAD。

## 架构文档
完整架构见 `docs/project-architecture.md`。

## 开发规范

### 数据流
所有模块通过 `lighting_agent/schemas.py` 中的 dataclass 传递数据，不允许跨模块直接引用内部实现。

### 模块边界
- `cad/` 只负责 DXF 读写，不调用 Radiance
- `radiance/` 只负责模型生成和仿真，不解析 IES
- `optimizer/` 通过 `radiance/runner.py` 调用仿真，不直接调用 Radiance 命令

### 测试
- 每个模块都有对应的测试文件在 `tests/`
- 运行测试：`pytest`
- 测试 fixtures（样本 DXF/IES）放在 `tests/fixtures/`

### Radiance 依赖
系统依赖 `oconv`, `rtrace`, `rpict`, `falsecolor`, `ies2rad`，运行前确认已安装：
```bash
./install.sh
```

## 常用命令
```bash
# 运行测试
pytest

# 启动 MCP Server
python -m mcp_server.server

# CLI 运行完整流程
lighting-agent run --dxf plan.dxf --ies ./ies/ --output ./output/
```
