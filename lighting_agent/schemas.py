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
