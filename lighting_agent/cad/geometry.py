from __future__ import annotations


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
