# Phase 1 — CAD Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a `.dwg` or `.dxf` file with closed polylines on the `LIGHT_ZONE` layer, return a validated `list[Room]` with coordinates in metres and room properties parsed from embedded TEXT entities.

**Architecture:** `schemas.py` defines the shared `Room` dataclass. `cad/geometry.py` provides coordinate conversion (mm→m) and polygon utilities. `cad/parser.py` opens the DXF (after auto-converting DWG via the existing `dwg_converter.py`), finds `LIGHT_ZONE` polylines, matches property TEXT entities to their polygons, and returns `list[Room]`. All tests use programmatically generated DXF fixtures (via ezdxf) — no binary fixtures committed.

**Tech Stack:** Python 3.11, ezdxf, pytest

---

## Files

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `lighting_agent/schemas.py` | Room, Luminaire, SimulationResult, ProjectConfig dataclasses |
| Create | `lighting_agent/cad/geometry.py` | mm→m conversion, polygon validation, area, point-in-polygon, bounding box |
| Create | `lighting_agent/cad/parser.py` | Open DXF, extract LIGHT_ZONE polylines + TEXT props, return list[Room] |
| Create | `tests/conftest.py` | Pytest fixtures: DXF files built with ezdxf in tmp_path |
| Create | `tests/test_cad_geometry.py` | Unit tests for geometry.py |
| Create | `tests/test_cad_parser.py` | Unit tests for parser.py |
| Modify | `tests/test_dwg_converter.py` | Tests for the already-implemented dwg_converter.py |
| Create | `docs/cad-layer-convention.md` | User-facing CAD drawing guide |

Already done — do NOT rewrite:
- `lighting_agent/cad/dwg_converter.py` ✅

---

## Task 1: Install Dependencies & Verify Environment

**Files:** none (shell only)

- [ ] **Step 1: Install ezdxf and pytest**

```bash
cd "/Users/jimmyzhao/Library/CloudStorage/OneDrive-个人/星恪/1 流程/Total solution/照度计算/lighting-agent"
pip install ezdxf pytest
```

- [ ] **Step 2: Verify ezdxf imports correctly**

```bash
python -c "import ezdxf; print('ezdxf', ezdxf.__version__)"
```

Expected output: `ezdxf 1.x.x` (any 1.x version)

---

## Task 2: schemas.py — Shared Data Structures

**Files:**
- Create: `lighting_agent/schemas.py`

- [ ] **Step 1: Write the schemas**

```python
# lighting_agent/schemas.py
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Room:
    name: str
    polygon: list[tuple[float, float]]   # XY vertices in metres
    height: float                         # room height in metres
    work_plane_height: float = 0.0
    target_lux: float = 300.0
    mount_height: float | None = None    # defaults to height if None

    def __post_init__(self) -> None:
        if self.mount_height is None:
            self.mount_height = self.height


@dataclass
class Luminaire:
    ies_path: str
    x: float   # metres
    y: float
    z: float
    rotation_deg: float = 0.0


@dataclass
class SimulationResult:
    room_name: str
    luminaires: list[Luminaire]
    illuminance_grid: list[list[float]]  # 2-D lux values
    grid_resolution: float               # metres between grid points
    avg_lux: float
    min_lux: float
    max_lux: float
    uniformity: float                    # Emin / Eave
    meets_target: bool
    target_lux: float


@dataclass
class ProjectConfig:
    cad_path: str                        # .dwg or .dxf
    ies_dir: str
    output_dir: str
    rooms: list[Room] = field(default_factory=list)
```

- [ ] **Step 2: Verify it imports**

```bash
python -c "from lighting_agent.schemas import Room, Luminaire, SimulationResult, ProjectConfig; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add lighting_agent/schemas.py
git commit -m "feat: add schemas dataclasses (Room, Luminaire, SimulationResult, ProjectConfig)"
```

---

## Task 3: Test Fixtures (conftest.py)

**Files:**
- Create: `tests/conftest.py`

These fixtures are used by both `test_cad_geometry.py` and `test_cad_parser.py`.

- [ ] **Step 1: Write conftest.py**

```python
# tests/conftest.py
import pytest
import ezdxf


def _make_dxf_with_zone(tmp_path, filename, polygons_mm, prop_texts=None):
    """Helper: create a DXF with LIGHT_ZONE polylines and optional property TEXT entities."""
    doc = ezdxf.new()
    doc.layers.add("LIGHT_ZONE", color=3)
    msp = doc.modelspace()
    prop_texts = prop_texts or [None] * len(polygons_mm)
    for pts, prop_text in zip(polygons_mm, prop_texts):
        msp.add_lwpolyline(pts, dxfattribs={"layer": "LIGHT_ZONE", "closed": True})
        if prop_text:
            # Place text at centroid of bounding box
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx = (min(xs) + max(xs)) / 2
            cy = (min(ys) + max(ys)) / 2
            msp.add_text(
                prop_text,
                dxfattribs={"layer": "LIGHT_ZONE", "insert": (cx, cy), "height": 200},
            )
    path = tmp_path / filename
    doc.saveas(str(path))
    return path


@pytest.fixture
def simple_room_dxf(tmp_path):
    """One 10×10 m room (10 000×10 000 mm) with height=9, target=150, mount=9."""
    return _make_dxf_with_zone(
        tmp_path,
        "simple_room.dxf",
        [[(0, 0), (10000, 0), (10000, 10000), (0, 10000)]],
        ["height=9;target=150;mount=9"],
    )


@pytest.fixture
def two_rooms_dxf(tmp_path):
    """Two rooms: 10×10 m and 5×8 m with different properties."""
    return _make_dxf_with_zone(
        tmp_path,
        "two_rooms.dxf",
        [
            [(0, 0), (10000, 0), (10000, 10000), (0, 10000)],
            [(12000, 0), (17000, 0), (17000, 8000), (12000, 8000)],
        ],
        ["height=9;target=150;mount=9", "height=4;target=300;mount=3.5"],
    )


@pytest.fixture
def no_props_dxf(tmp_path):
    """LIGHT_ZONE polygon with no TEXT entity — parser must use defaults."""
    return _make_dxf_with_zone(
        tmp_path,
        "no_props.dxf",
        [[(0, 0), (6000, 0), (6000, 6000), (0, 6000)]],
        [None],
    )


@pytest.fixture
def empty_dxf(tmp_path):
    """DXF with no LIGHT_ZONE entities at all."""
    doc = ezdxf.new()
    path = tmp_path / "empty.dxf"
    doc.saveas(str(path))
    return path
```

- [ ] **Step 2: Verify fixtures load without error**

```bash
cd "/Users/jimmyzhao/Library/CloudStorage/OneDrive-个人/星恪/1 流程/Total solution/照度计算/lighting-agent"
python -c "import tests.conftest; print('conftest OK')"
```

Expected: `conftest OK`

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add pytest DXF fixtures (simple_room, two_rooms, no_props, empty)"
```

---

## Task 4: TDD — cad/geometry.py

**Files:**
- Create: `tests/test_cad_geometry.py`
- Create: `lighting_agent/cad/geometry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cad_geometry.py
import pytest
from lighting_agent.cad.geometry import (
    mm_to_m,
    vertices_mm_to_m,
    validate_polygon,
    polygon_area,
    point_in_polygon,
    bounding_box,
)


def test_mm_to_m_converts_correctly():
    assert mm_to_m(1000.0) == pytest.approx(1.0)
    assert mm_to_m(0.0) == 0.0
    assert mm_to_m(500.0) == pytest.approx(0.5)


def test_vertices_mm_to_m():
    verts_mm = [(0, 0), (10000, 0), (10000, 10000), (0, 10000)]
    result = vertices_mm_to_m(verts_mm)
    assert result == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_validate_polygon_accepts_triangle():
    validate_polygon([(0, 0), (1, 0), (0, 1)])  # must not raise


def test_validate_polygon_rejects_two_points():
    with pytest.raises(ValueError, match="at least 3"):
        validate_polygon([(0, 0), (1, 0)])


def test_polygon_area_square():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert polygon_area(square) == pytest.approx(100.0)


def test_polygon_area_triangle():
    # Right triangle: base=4, height=3 → area=6
    tri = [(0, 0), (4, 0), (0, 3)]
    assert polygon_area(tri) == pytest.approx(6.0)


def test_point_in_polygon_inside():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5.0, 5.0), square) is True


def test_point_in_polygon_outside():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((15.0, 5.0), square) is False


def test_bounding_box():
    verts = [(1, 2), (5, 3), (2, 8)]
    assert bounding_box(verts) == (1, 2, 5, 8)
```

- [ ] **Step 2: Run tests — confirm they all FAIL**

```bash
pytest tests/test_cad_geometry.py -v
```

Expected: `ModuleNotFoundError: No module named 'lighting_agent.cad.geometry'`

- [ ] **Step 3: Implement geometry.py**

```python
# lighting_agent/cad/geometry.py


def mm_to_m(value: float) -> float:
    return value / 1000.0


def vertices_mm_to_m(
    vertices: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    return [(mm_to_m(x), mm_to_m(y)) for x, y in vertices]


def validate_polygon(vertices: list[tuple[float, float]]) -> None:
    if len(vertices) < 3:
        raise ValueError(
            f"Polygon needs at least 3 vertices, got {len(vertices)}"
        )


def polygon_area(vertices: list[tuple[float, float]]) -> float:
    """Shoelace formula."""
    n = len(vertices)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    return abs(area) / 2.0


def point_in_polygon(
    point: tuple[float, float],
    polygon: list[tuple[float, float]],
) -> bool:
    """Ray-casting algorithm."""
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def bounding_box(
    vertices: list[tuple[float, float]],
) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y)."""
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    return min(xs), min(ys), max(xs), max(ys)
```

- [ ] **Step 4: Run tests — confirm they all PASS**

```bash
pytest tests/test_cad_geometry.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add lighting_agent/cad/geometry.py tests/test_cad_geometry.py
git commit -m "feat: add cad/geometry.py with mm→m conversion and polygon utilities"
```

---

## Task 5: TDD — cad/parser.py

**Files:**
- Create: `tests/test_cad_parser.py`
- Create: `lighting_agent/cad/parser.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cad_parser.py
import pytest
from lighting_agent.cad.parser import parse_rooms
from lighting_agent.schemas import Room


def test_parse_single_room_count(simple_room_dxf):
    rooms = parse_rooms(str(simple_room_dxf))
    assert len(rooms) == 1


def test_parse_single_room_type(simple_room_dxf):
    rooms = parse_rooms(str(simple_room_dxf))
    assert isinstance(rooms[0], Room)


def test_parse_single_room_properties(simple_room_dxf):
    room = parse_rooms(str(simple_room_dxf))[0]
    assert room.height == pytest.approx(9.0)
    assert room.target_lux == pytest.approx(150.0)
    assert room.mount_height == pytest.approx(9.0)


def test_parse_single_room_mm_to_m_conversion(simple_room_dxf):
    room = parse_rooms(str(simple_room_dxf))[0]
    # 10 000 mm → 10.0 m
    xs = [p[0] for p in room.polygon]
    assert max(xs) == pytest.approx(10.0)


def test_parse_single_room_polygon_vertex_count(simple_room_dxf):
    room = parse_rooms(str(simple_room_dxf))[0]
    assert len(room.polygon) == 4


def test_parse_two_rooms(two_rooms_dxf):
    rooms = parse_rooms(str(two_rooms_dxf))
    assert len(rooms) == 2


def test_parse_two_rooms_different_properties(two_rooms_dxf):
    rooms = parse_rooms(str(two_rooms_dxf))
    targets = {r.target_lux for r in rooms}
    assert targets == {150.0, 300.0}


def test_parse_no_props_uses_defaults(no_props_dxf):
    room = parse_rooms(str(no_props_dxf))[0]
    assert room.height == pytest.approx(3.0)
    assert room.target_lux == pytest.approx(300.0)


def test_parse_no_props_mount_defaults_to_height(no_props_dxf):
    room = parse_rooms(str(no_props_dxf))[0]
    assert room.mount_height == pytest.approx(room.height)


def test_parse_empty_dxf_returns_empty_list(empty_dxf):
    assert parse_rooms(str(empty_dxf)) == []
```

- [ ] **Step 2: Run tests — confirm they all FAIL**

```bash
pytest tests/test_cad_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'lighting_agent.cad.parser'`

- [ ] **Step 3: Implement parser.py**

```python
# lighting_agent/cad/parser.py
from __future__ import annotations
from pathlib import Path

import ezdxf

from .dwg_converter import ensure_dxf
from .geometry import vertices_mm_to_m, validate_polygon, point_in_polygon
from ..schemas import Room

LIGHT_ZONE_LAYER = "LIGHT_ZONE"
_DEFAULT_HEIGHT = 3.0
_DEFAULT_TARGET_LUX = 300.0
_DEFAULT_WORK_PLANE = 0.0


def _parse_props(text: str) -> dict[str, str]:
    """'height=9;target=150;mount=9' → {'height': '9', 'target': '150', 'mount': '9'}"""
    props: dict[str, str] = {}
    for part in text.strip().split(";"):
        if "=" in part:
            key, _, val = part.partition("=")
            props[key.strip()] = val.strip()
    return props


def _float_prop(props: dict[str, str], key: str, default: float) -> float:
    try:
        return float(props[key]) if key in props else default
    except ValueError:
        return default


def _extract_polylines(msp) -> list[list[tuple[float, float]]]:
    polys: list[list[tuple[float, float]]] = []
    for entity in msp.query(f'LWPOLYLINE[layer=="{LIGHT_ZONE_LAYER}"]'):
        verts = [(p[0], p[1]) for p in entity.get_points()]
        if len(verts) >= 3:
            polys.append(verts)
    return polys


def _match_props(
    msp, polygons_mm: list[list[tuple[float, float]]]
) -> list[dict[str, str]]:
    """Find TEXT/MTEXT on LIGHT_ZONE layer; assign each to the polygon that contains it."""
    props_list: list[dict[str, str]] = [{} for _ in polygons_mm]
    for entity in msp.query(f'[layer=="{LIGHT_ZONE_LAYER}"]'):
        if entity.dxftype() not in ("TEXT", "MTEXT"):
            continue
        insert = entity.dxf.insert
        point = (insert.x, insert.y)
        raw = (
            entity.plain_mtext()
            if entity.dxftype() == "MTEXT"
            else entity.dxf.text
        )
        props = _parse_props(raw)
        if not props:
            continue
        for i, poly in enumerate(polygons_mm):
            if point_in_polygon(point, poly):
                props_list[i].update(props)
                break
    return props_list


def parse_rooms(cad_path: str, tmp_dir: str | None = None) -> list[Room]:
    """Parse a DWG or DXF file; return all LIGHT_ZONE rooms as Room objects."""
    dxf_path, was_converted = ensure_dxf(cad_path, tmp_dir=tmp_dir)
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        polys_mm = _extract_polylines(msp)
        if not polys_mm:
            return []
        props_list = _match_props(msp, polys_mm)
        rooms: list[Room] = []
        for i, (verts_mm, props) in enumerate(zip(polys_mm, props_list)):
            validate_polygon(verts_mm)
            verts_m = vertices_mm_to_m(verts_mm)
            height = _float_prop(props, "height", _DEFAULT_HEIGHT)
            target = _float_prop(props, "target", _DEFAULT_TARGET_LUX)
            mount = _float_prop(props, "mount", height)
            work_plane = _float_prop(props, "work_plane", _DEFAULT_WORK_PLANE)
            name = props.get("name", f"zone_{i + 1}")
            rooms.append(
                Room(
                    name=name,
                    polygon=verts_m,
                    height=height,
                    work_plane_height=work_plane,
                    target_lux=target,
                    mount_height=mount,
                )
            )
        return rooms
    finally:
        if was_converted:
            dxf_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests — confirm they all PASS**

```bash
pytest tests/test_cad_parser.py -v
```

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add lighting_agent/cad/parser.py tests/test_cad_parser.py
git commit -m "feat: implement cad/parser.py — parse LIGHT_ZONE polylines and TEXT props from DXF"
```

---

## Task 6: Tests for dwg_converter.py

**Files:**
- Modify: `tests/test_dwg_converter.py`

`dwg_converter.py` is already implemented. This task writes the tests.

- [ ] **Step 1: Write the tests**

```python
# tests/test_dwg_converter.py
import shutil
import pytest
from pathlib import Path
from lighting_agent.cad.dwg_converter import is_dwg, ensure_dxf


def test_is_dwg_returns_true_for_dwg():
    assert is_dwg("plan.dwg") is True
    assert is_dwg(Path("floor.DWG")) is True


def test_is_dwg_returns_false_for_dxf():
    assert is_dwg("plan.dxf") is False
    assert is_dwg(Path("floor.DXF")) is False


def test_ensure_dxf_passthrough_for_dxf(simple_room_dxf):
    dxf_path, was_converted = ensure_dxf(simple_room_dxf)
    assert dxf_path == simple_room_dxf
    assert was_converted is False


def test_ensure_dxf_raises_file_not_found_for_missing_dwg():
    with pytest.raises(FileNotFoundError):
        ensure_dxf(Path("/nonexistent/file.dwg"))


def test_ensure_dxf_raises_if_dwg2dxf_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    fake_dwg = tmp_path / "test.dwg"
    fake_dwg.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="dwg2dxf not found"):
        ensure_dxf(fake_dwg)
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_dwg_converter.py -v
```

Expected: `5 passed`

- [ ] **Step 3: Commit**

```bash
git add tests/test_dwg_converter.py
git commit -m "test: add tests for cad/dwg_converter.py"
```

---

## Task 7: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
pytest -v
```

Expected: all tests pass, no warnings about missing imports.

- [ ] **Step 2: If any test fails, fix it before continuing**

Common issues:
- `ImportError` for `lighting_agent` → run `pip install -e .` first
- `ezdxf` version mismatch → `pip install --upgrade ezdxf`

---

## Task 8: docs/cad-layer-convention.md

**Files:**
- Create: `docs/cad-layer-convention.md`

- [ ] **Step 1: Write the doc**

```markdown
# CAD 图层规范 — LightingAgent

## 快速上手

1. 在 AutoCAD / BricsCAD / LibreCAD 中打开你的平面图
2. 新建图层，命名为 `LIGHT_ZONE`（大写，完全匹配）
3. 在该图层上，用 **LWPOLYLINE（多段线）** 画出需要计算照度的区域，**必须闭合**
4. 在多边形**内部**添加单行文字（TEXT），填写房间参数（见下方格式）
5. 保存为 `.dxf` 或 `.dwg` 格式

---

## 参数文字格式

文字内容使用分号分隔的键值对：

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

同一个 DXF 文件可以有多个 `LIGHT_ZONE` 多边形，每个对应一个独立的区域，分别进行照度计算。每个多边形内放一段属性文字。

---

## 坐标单位

DXF 内部坐标单位为 **毫米（mm）**，LightingAgent 读取后自动转换为米（m）。

---

## 写回图层

LightingAgent 计算完成后，在图层 `LIGHT_LAYOUT` 上添加灯具符号和标注。原始图层不修改。

---

## 常见问题

**Q: 多段线没有被识别怎么办？**
检查图层名是否严格为 `LIGHT_ZONE`（区分大小写）；确认多段线是否已闭合（CLOSE 属性为 Yes）。

**Q: 属性文字没有被读取怎么办？**
确认文字在多边形内部；确认文字图层为 `LIGHT_ZONE`；确认格式为 `key=value;key=value`。

**Q: 输入的是 DWG 格式，需要提前转换吗？**
不需要。LightingAgent 自动调用 `dwg2dxf` 转换，支持 AutoCAD R13 ~ 2018 格式。
```

- [ ] **Step 2: Commit**

```bash
git add docs/cad-layer-convention.md
git commit -m "docs: add CAD layer convention guide for users"
```

---

## Task 9: Final Push & task_plan.md Update

- [ ] **Step 1: Push all commits**

```bash
git push
```

- [ ] **Step 2: Update task_plan.md — mark Phase 1 tasks complete**

In `task_plan.md`, change all Phase 1 rows from `⬜ 待开始` to `✅ 完成`.

- [ ] **Step 3: Commit and push task_plan update**

```bash
git add task_plan.md
git commit -m "chore: mark Phase 1 complete in task_plan.md"
git push
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ `cad/dwg_converter.py` — already done, tests added in Task 6
- ✅ `cad/parser.py` — Task 5
- ✅ `cad/geometry.py` — Task 4
- ✅ `schemas.py` — Task 2
- ✅ Test fixtures — Task 3
- ✅ `test_cad_geometry.py` — Task 4
- ✅ `test_cad_parser.py` — Task 5
- ✅ `test_dwg_converter.py` — Task 6
- ✅ `docs/cad-layer-convention.md` — Task 8

**Placeholder scan:** None found — all steps have full code.

**Type consistency:**
- `parse_rooms(cad_path: str)` → `list[Room]` — consistent throughout
- `ensure_dxf(cad_path)` → `tuple[Path, bool]` — matches dwg_converter.py signature
- `vertices_mm_to_m(list[tuple[float,float]])` → `list[tuple[float,float]]` — consistent
- `Room.mount_height: float | None` → set to float in `__post_init__` before any caller uses it
