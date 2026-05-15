# Task Plan — LightingAgent

## 当前目标

完成 Phase 2：Radiance 模型生成，给定 Room 数据能完成一次仿真并返回照度数值。

---

## Phase 1：CAD 解析 + DWG 支持✅ 已完成

**里程碑**：给定 `.dwg` 或 `.dxf`，能正确输出 `list[Room]` ✅

| # | 任务 | 文件 | 状态 |
|---|------|------|------|
| 1.1 | 封装 `dwg2dxf`，自动检测 DWG/DXF 输入 | `cad/dwg_converter.py` | ✅ 完成 |
| 1.2 | 读取 DXF，识别 `LIGHT_ZONE` 图层的闭合多边形 | `cad/parser.py` | ✅ 完成 |
| 1.3 | 坐标转换（mm → m），多边形工具函数 | `cad/geometry.py` | ✅ 完成 |
| 1.4 | 单元测试：DWG 转换 | `tests/test_dwg_converter.py` | ✅ 完成 |
| 1.5 | 单元测试：DXF 解析 | `tests/test_cad_parser.py` | ✅ 完成 |
| 1.6 | 测试 fixtures（程序化生成 DXF） | `tests/conftest.py` | ✅ 完成 |
| 1.7 | 编写 CAD 图层规范文档 | `docs/cad-layer-convention.md` | ⬜ 待开始 |

---

## Phase 2：Radiance 模型生成（第 2 周）

**里程碑**：给定 Room，能完成一次 Radiance 仿真并返回照度数值

| # | 任务 | 文件 | 状态 |
|---|------|------|------|
| 2.1 | 定义标准材质（地板 0.2、墙 0.5、天花板 0.7） | `radiance/materials.py` | ⬜ 待开始 |
| 2.2 | 从 Room 生成 `.rad` 场景文件，调用 `oconv` | `radiance/model_builder.py` | ⬜ 待开始 |
| 2.3 | 生成传感器网格 `.pts`，调用 `rtrace` | `radiance/runner.py` | ⬜ 待开始 |
| 2.4 | 解析 rtrace 输出为照度矩阵 | `radiance/result_parser.py` | ⬜ 待开始 |
| 2.5 | 单元测试 | `tests/test_radiance_builder.py` | ⬜ 待开始 |

---

## Phase 3：IES 文件处理（第 2 周末）

**里程碑**：给定 IES 目录，能列出所有灯具并转换为 Radiance 格式

| # | 任务 | 文件 | 状态 |
|---|------|------|------|
| 3.1 | 扫描目录，解析 IES 文件头信息 | `ies/loader.py` | ⬜ 待开始 |
| 3.2 | 封装 `ies2rad`，生成 Radiance 光源 | `ies/converter.py` | ⬜ 待开始 |
| 3.3 | 单元测试 | `tests/test_ies_loader.py` | ⬜ 待开始 |

---

## Phase 4：布灯优化器（第 3 周）

**里程碑**：优化器能自动找到灯具数量最少的合规方案

| # | 任务 | 文件 | 状态 |
|---|------|------|------|
| 4.1 | 生成 nx×ny 均匀网格候选方案 | `optimizer/grid.py` | ⬜ 待开始 |
| 4.2 | 照度指标校验（平均值、最小值、均匀度≥0.4） | `optimizer/checker.py` | ⬜ 待开始 |
| 4.3 | 迭代优化主循环（最多 10 次） | `optimizer/optimizer.py` | ⬜ 待开始 |
| 4.4 | 单元测试 | `tests/test_optimizer.py` | ⬜ 待开始 |

---

## Phase 5：报告生成（第 4 周）

**里程碑**：给定 DWG + IES，自动输出 PDF 报告 + 标注 DXF

| # | 任务 | 文件 | 状态 |
|---|------|------|------|
| 5.1 | 调用 `falsecolor` 生成伪彩色 PNG | `reporter/falsecolor.py` | ⬜ 待开始 |
| 5.2 | 生成完整 PDF 报告 | `reporter/pdf_report.py` | ⬜ 待开始 |
| 5.3 | 在 DXF 上绘制灯具符号和标注 | `cad/writer.py` | ⬜ 待开始 |
| 5.4 | 串联全流程 | `lighting_agent/pipeline.py` | ⬜ 待开始 |
| 5.5 | 端到端测试 | `tests/test_pipeline.py` | ⬜ 待开始 |

---

## Phase 6：MCP Server + CLI + 发布（第 5-6 周）

**里程碑**：Claude Code 能通过 tool call 完成完整布灯设计

| # | 任务 | 文件 | 状态 |
|---|------|------|------|
| 6.1 | 定义所有 MCP tool | `mcp_server/tools.py` | ⬜ 待开始 |
| 6.2 | FastMCP server 入口 | `mcp_server/server.py` | ⬜ 待开始 |
| 6.3 | Click CLI | `cli/main.py` | ⬜ 待开始 |
| 6.4 | `.mcp.json` 配置，Claude Code 端到端测试 | 项目根目录 | ⬜ 待开始 |
| 6.5 | 完善 README，干净 Mac 安装测试 | `README.md` | ⬜ 待开始 |
| 6.6 | 打 v0.1.0 tag 发布 | GitHub | ⬜ 待开始 |

---

## 已遇到的问题

| 错误 | 尝试 | 解决方案 |
|------|------|---------|
| — | — | — |

---

## 已定设计决策（不重新讨论）

- 仿真引擎：Radiance（LEED 认证，物理精度高）
- DWG 转换：LibreDWG `dwg2dxf`（支持 R13~2018）
- 数据结构：`schemas.py` dataclass（所有模块间传递）
- 对外接口：FastMCP + Click CLI
- 优化策略：网格枚举（初版），后续可扩展
