import math
import re
from dataclasses import dataclass


NUMBER = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?)"
POINT_RE = re.compile(
    r"CARTESIAN_POINT\s*\([^()]*,\s*\(\s*"
    + NUMBER
    + r"\s*,\s*"
    + NUMBER
    + r"\s*,\s*"
    + NUMBER
    + r"\s*\)\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StepFeatures:
    bbox_length: float
    bbox_width: float
    bbox_height: float
    bbox_volume: float
    bbox_diagonal: float
    point_count: int


def extract_step_features(data: bytes) -> StepFeatures | None:
    text = data.decode("utf-8", errors="ignore")
    points = [(float(x), float(y), float(z)) for x, y, z in POINT_RE.findall(text)]
    if not points:
        return None

    xs, ys, zs = zip(*points)
    spans = sorted(
        [
            max(xs) - min(xs),
            max(ys) - min(ys),
            max(zs) - min(zs),
        ],
        reverse=True,
    )
    length, width, height = spans
    volume = length * width * height
    diagonal = math.sqrt(length**2 + width**2 + height**2)
    return StepFeatures(
        bbox_length=round(length, 4),
        bbox_width=round(width, 4),
        bbox_height=round(height, 4),
        bbox_volume=round(volume, 4),
        bbox_diagonal=round(diagonal, 4),
        point_count=len(points),
    )
