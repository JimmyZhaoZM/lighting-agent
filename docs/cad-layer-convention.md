# CAD 图层规范 — LightingAgent

## 快速上手

1. 在 AutoCAD / BricsCAD / LibreCAD 中打开你的平面图
2. 新建图层，命名为 `LIGHT_ZONE`（大写，完全匹配）
3. 在该图层上，用 **LWPOLYLINE（多段线）** 画出需要计算照度的区域，**必须闭合**
4. 在多边形**内部**添加单行文字（TEXT），填写房间参数（见下方格式）
5. 保存为 `.dxf` 或 `.dwg` 格式

---

## 参数文字格式

文字内容使用分号分隔的键值对，放在多边形内部的 `LIGHT_ZONE` 图层上：

```
height=<层高m>;target=<目标照度lux>;mount=<安装高度m>
```

**示例：**
```
height=9;target=150;mount=9
```

| 参数 | 含义 | 单位 | 不填时默认值 |
|------|------|------|------------|
| `height` | 房间层高 | m | 3.0 |
| `target` | 目标平均照度 | lux | 300 |
| `mount` | 灯具安装高度 | m | 等于 height |
| `work_plane` | 工作面高度（计算面） | m | 0.0（地面） |
| `name` | 区域名称（出现在报告中） | — | zone_1, zone_2… |

---

## 完整示例

```
height=4.5;target=500;mount=4.0;work_plane=0.8;name=办公区A
```

---

## 多区域

同一个 DXF/DWG 文件可以包含多个 `LIGHT_ZONE` 多边形，每个对应一个独立的照度计算区域。每个多边形内放一段属性文字。

---

## 坐标单位

DXF 内部坐标单位为 **毫米（mm）**，LightingAgent 读取后自动转换为米（m）。

---

## 写回图层

LightingAgent 计算完成后，在图层 `LIGHT_LAYOUT` 上添加灯具符号和标注，原始图层不修改。

---

## 常见问题

**Q: 多段线没有被识别怎么办？**
检查图层名是否严格为 `LIGHT_ZONE`（区分大小写）；确认多段线已闭合（CLOSE 属性为 Yes）。

**Q: 属性文字没有被读取怎么办？**
确认文字在多边形内部；确认文字图层为 `LIGHT_ZONE`；确认格式为 `key=value;key=value`。

**Q: 输入的是 DWG 格式，需要提前转换吗？**
不需要，LightingAgent 自动完成转换。转换工具优先级：
1. **ODA File Converter**（推荐，支持所有 AutoCAD 版本）— 需手动安装到 `/Applications/ODAFileConverter.app`，下载地址：https://www.opendesign.com/guestfiles/oda_file_converter
2. **LibreDWG `dwg2dxf`**（备用，`brew install libredwg`，支持 R13 ~ 2018）

至少安装其中一个才能使用 DWG 输入。
