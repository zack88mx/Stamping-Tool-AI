import re
from statistics import mean

from .models import AwardedJob
from .schemas import QuoteRange, QuoteSearchInput


WEIGHTS = {
    "material_thickness": 20,
    "part_die_size": 20,
    "number_of_stations": 20,
    "die_type": 15,
    "customer_type": 10,
    "actual_hours": 10,
    "notes_complexity": 5,
}


def _text(value: str | None) -> str:
    return (value or "").strip().lower()


def _exact_score(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return 1.0 if _text(a) == _text(b) else 0.0


def _numeric_similarity(target: float | None, candidate: float | None) -> float:
    if target is None or candidate is None:
        return 0.0
    if target == 0 and candidate == 0:
        return 1.0
    baseline = max(abs(target), abs(candidate), 1.0)
    return max(0.0, 1.0 - abs(target - candidate) / baseline)


def _average(values: list[float]) -> float:
    useful = [value for value in values if value > 0]
    return sum(useful) / len(useful) if useful else 0.0


def _die_volume(length: float | None, width: float | None, height: float | None) -> float | None:
    if length is None or width is None or height is None:
        return None
    return length * width * height


def _notes_similarity(a: str | None, b: str | None) -> float:
    left = set(re.findall(r"[a-z0-9]+", _text(a)))
    right = set(re.findall(r"[a-z0-9]+", _text(b)))
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def score_job(input_data: QuoteSearchInput, job: AwardedJob) -> tuple[float, dict[str, float]]:
    material_score = _exact_score(input_data.material, job.material)
    thickness_score = _numeric_similarity(input_data.material_thickness, job.material_thickness)
    material_thickness = _average([material_score, thickness_score])

    target_volume = _die_volume(input_data.die_length, input_data.die_width, input_data.die_height)
    candidate_volume = _die_volume(job.die_length, job.die_width, job.die_height)
    part_die_size = _numeric_similarity(target_volume, candidate_volume)

    breakdown = {
        "material_thickness": material_thickness * WEIGHTS["material_thickness"],
        "part_die_size": part_die_size * WEIGHTS["part_die_size"],
        "number_of_stations": _numeric_similarity(
            input_data.number_of_stations,
            job.number_of_stations,
        )
        * WEIGHTS["number_of_stations"],
        "die_type": _exact_score(input_data.die_type, job.die_type) * WEIGHTS["die_type"],
        "customer_type": _exact_score(input_data.customer_type, job.customer_type)
        * WEIGHTS["customer_type"],
        "actual_hours": _numeric_similarity(input_data.actual_tool_build_hours, job.actual_tool_build_hours)
        * WEIGHTS["actual_hours"],
        "notes_complexity": _notes_similarity(
            " ".join(filter(None, [input_data.notes, input_data.lessons_learned])),
            " ".join(filter(None, [job.notes, job.lessons_learned])),
        )
        * WEIGHTS["notes_complexity"],
    }
    return round(sum(breakdown.values()), 2), {k: round(v, 2) for k, v in breakdown.items()}


def suggested_range(scored_jobs: list[tuple[AwardedJob, float, dict[str, float]]]) -> QuoteRange:
    priced = [
        (job.awarded_price, score)
        for job, score, _ in scored_jobs
        if job.awarded_price is not None and score > 0
    ][:10]
    if not priced:
        return QuoteRange(low=None, high=None, average=None, basis_count=0)

    total_weight = sum(score for _, score in priced)
    weighted_average = sum(price * score for price, score in priced) / total_weight
    prices = [price for price, _ in priced]
    spread = 0.12 if len(prices) < 3 else 0.18
    low = min(min(prices), weighted_average * (1 - spread))
    high = max(max(prices), weighted_average * (1 + spread))

    return QuoteRange(
        low=round(low, 2),
        high=round(high, 2),
        average=round(mean(prices), 2),
        basis_count=len(priced),
    )
