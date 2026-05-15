# LightingAgent — Claude Code 项目指南

> **每次新 session 开始时**，先读本文件，再读 `task_plan.md` 和 `progress.md`，然后继续工作。

## 项目目标

AI 驱动的照度计算与布灯设计系统。输入 CAD 图纸（DWG/DXF）+ IES 文件 + 照度要求，输出优化的布灯方案、PDF 报告和标注 CAD。

## 当前状态

- **当前 Phase：Phase 1 — CAD 解析 + DWG 支持**
- **完成状态：Phase 0 ✅ 已完成（项目骨架已搭建）**
- 详细任务进度见 `task_plan.md`

## 技术栈

Python 3.11+、Radiance（brew）、LibreDWG（brew）、ezdxf、numpy、scipy、reportlab、FastMCP、Click

## 核心数据结构（唯一真相来源）

所有模块通过 `lighting_agent/schemas.py` 的 dataclass 传递数据：

```
Room → [radiance/] → SimulationResult
Room → [optimizer/] → list[Luminaire] → SimulationResult
ProjectConfig → pipeline.py → 串联全流程
```

## 模块边界（不可越界）

| 模块 | 职责 | 不允许 |
|------|------|--------|
| `cad/` | DXF 读写、坐标转换 | 不调用 Radiance |
| `radiance/` | 场景生成、仿真执行 | 不解析 IES |
| `ies/` | IES 加载、转换为 rad | 不涉及几何 |
| `optimizer/` | 布灯迭代优化 | 不直接调用 Radiance 命令（通过 runner.py） |
| `reporter/` | PDF + 伪彩色图 | 不修改仿真逻辑 |

## CAD 图层约定

- `LIGHT_ZONE` — 照度计算区域（闭合 LWPOLYLINE）
- 图层备注格式：`height=5.5;target=300;mount=4.8`
- 坐标单位：DXF 内为 mm，Python 内统一转换为 m
- 写回图层：`LIGHT_LAYOUT`

## 关键设计决策（已定，不重新讨论）

- **仿真引擎**：Radiance（LEED 认证，支持 IES 配光曲线，支持非矩形房间）
- **DWG 转换**：LibreDWG `dwg2dxf`（支持 R13~2018）
- **对外接口**：FastMCP Server（tool call）+ Click CLI
- **优化策略**：先简单网格枚举（nx×ny），后续可扩展遗传算法

## 测试规范

```bash
pytest                          # 运行全部测试
pytest tests/test_cad_parser.py # 运行单个模块测试
```

- 每个模块对应 `tests/test_<module>.py`
- 测试 fixtures 放 `tests/fixtures/`（DXF/IES 样本文件）

## 常用命令

```bash
./install.sh                                          # 安装依赖
python -m mcp_server.server                           # 启动 MCP Server
lighting-agent run --dxf plan.dxf --ies ./ies/ --output ./output/  # CLI
which oconv rtrace rpict falsecolor ies2rad dwg2dxf   # 验证 Radiance 安装
```

## 完整架构参考

`docs/project-architecture.md` — 包含目录结构、数据结构定义、各模块职责、MCP 工具定义、完整工作流、Roadmap。
