# LightingAgent — Agent 协作指南

> 适用于所有 AI agent（Cursor、Windsurf、Gemini、Copilot 等）。
> **开始工作前必读**：本文件 → `task_plan.md` → `progress.md`

## 项目简介

AI 驱动的照度计算与布灯设计系统。输入 CAD 图纸（DWG/DXF）+ IES 文件 + 照度要求，输出优化的布灯方案、PDF 报告和标注 CAD。

完整架构见 `docs/project-architecture.md`。

## 当前 Phase 状态

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 0 | 项目初始化、骨架搭建 | ✅ 完成 |
| Phase 1 | CAD 解析 + DWG 支持 | 🔄 进行中 |
| Phase 2 | Radiance 模型生成 | ⬜ 待开始 |
| Phase 3 | IES 文件处理 | ⬜ 待开始 |
| Phase 4 | 布灯优化器 | ⬜ 待开始 |
| Phase 5 | 报告生成 + pipeline | ⬜ 待开始 |
| Phase 6 | MCP Server + CLI + 发布 | ⬜ 待开始 |

**当前任务详情见 `task_plan.md`。**

## 目录结构速览

```
lighting-agent/
├── lighting_agent/
│   ├── schemas.py       ← 所有模块共用数据结构（唯一真相来源）
│   ├── pipeline.py      ← 主流程编排
│   ├── cad/             ← Phase 1：CAD 读写
│   ├── radiance/        ← Phase 2：Radiance 仿真
│   ├── ies/             ← Phase 3：IES 处理
│   ├── optimizer/       ← Phase 4：布灯优化
│   └── reporter/        ← Phase 5：报告生成
├── mcp_server/          ← Phase 6：MCP Server
├── cli/                 ← Phase 6：CLI
└── tests/               ← 每个模块对应测试文件
```

## 核心数据流

```
DWG/DXF → cad/parser.py → list[Room]
                                ↓
IES dir → ies/loader.py → list[IES]
                                ↓
             optimizer/optimizer.py（迭代调用 radiance/runner.py）
                                ↓
                        SimulationResult
                                ↓
             reporter/pdf_report.py → PDF + PNG
             cad/writer.py → 标注 DXF
```

## 模块边界规则

- `cad/` 只处理 DXF 读写，不调用 Radiance
- `radiance/` 只负责仿真，不解析 IES
- `optimizer/` 通过 `radiance/runner.py` 调用仿真，不直接执行 Radiance 命令
- 所有模块间数据传递**只用 `schemas.py` 中的 dataclass**，不传原始字典

## CAD 图层约定

- `LIGHT_ZONE`：照度计算区域（闭合 LWPOLYLINE）
- 图层备注：`height=5.5;target=300;mount=4.8`
- 坐标单位：DXF 内 mm，Python 内统一用 m
- 写回图层：`LIGHT_LAYOUT`

## 开发规范

1. **先看 schemas.py**：理解数据结构再动手写代码
2. **先写测试**：每个函数对应 `tests/test_<module>.py` 中的测试
3. **不修改已完成 Phase 的接口**：只能扩展，不破坏已有签名
4. **不重新讨论已定决策**：Radiance 引擎、LibreDWG 转换方案已定

## 测试与验证

```bash
pip install -e .             # 安装开发模式
pytest                       # 运行全部测试
pytest tests/test_cad_parser.py  # 运行单模块测试
./install.sh                 # 安装 Radiance + LibreDWG 系统依赖
which oconv rtrace rpict falsecolor ies2rad dwg2dxf  # 验证依赖
```

## 完成一个 Phase 后需要做的事

1. 在 `task_plan.md` 中将该 Phase 标记为 ✅ 完成
2. 在 `progress.md` 中记录完成时间和关键决策
3. 在 `findings.md` 中记录遇到的坑和解决方案
4. 通知用户更新 `CLAUDE.md` 和 `AGENTS.md` 中的状态表

## 外部依赖

| 工具 | 安装方式 | 用途 |
|------|---------|------|
| Radiance | `brew install radiance` | 照度仿真引擎 |
| LibreDWG | `brew install libredwg` | DWG → DXF 转换 |
| ezdxf | pip | DXF 读写 |
| FastMCP | pip | MCP Server 框架 |
