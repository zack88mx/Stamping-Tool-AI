import io
import re
from dataclasses import dataclass

from pypdf import PdfReader


MATERIAL_PATTERNS = [
    re.compile(r"\bMATERIAL\s*[:\-]?\s*([A-Z0-9][A-Z0-9 \-./]{2,60})", re.IGNORECASE),
    re.compile(r"\bMATL\.?\s*[:\-]?\s*([A-Z0-9][A-Z0-9 \-./]{2,60})", re.IGNORECASE),
    re.compile(r"\b(?:STEEL|STAINLESS|ALUMINUM|BRASS|COPPER)\b[ A-Z0-9\-./]*", re.IGNORECASE),
]
THICKNESS_PATTERNS = [
    re.compile(r"\b(?:THICKNESS|THK|THICK|GAUGE|GAGE)\s*[:\-]?\s*([0-9]*\.?[0-9]+)", re.IGNORECASE),
    re.compile(r"\b([0-9]*\.?[0-9]+)\s*(?:IN|MM)?\s*(?:THK|THICK)\b", re.IGNORECASE),
]
TOLERANCE_RE = re.compile(r"(?:\+/\-|\+-|±)\s*([0-9]*\.?[0-9]+)|\b0?\.0{1,4}[0-9]+\b")
DATUM_RE = re.compile(r"\bDATUM\b|\bDATUMS\b|\b[A-Z]\s*\|\s*[A-Z]\b", re.IGNORECASE)
GDT_TERMS = [
    "POSITION",
    "TRUE POSITION",
    "FLATNESS",
    "PROFILE",
    "PARALLELISM",
    "PERPENDICULARITY",
    "ANGULARITY",
    "CONCENTRICITY",
    "CIRCULARITY",
    "CYLINDRICITY",
    "RUNOUT",
    "TOTAL RUNOUT",
    "STRAIGHTNESS",
]
BAD_MATERIAL_VALUES = {
    "DRAWN BY",
    "ENGINEER",
    "SIZE",
    "SHEET",
    "SCALE",
    "DWG",
    "DWG.",
    "DWG. NO.",
    "REV",
}


@dataclass(frozen=True)
class PrintFeatures:
    material_spec: str | None
    thickness: float | None
    gdt_callout_count: int
    tolerance_count: int
    datum_count: int
    tightest_tolerance: float | None
    extracted_text: str


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.replace("\n", " ").split())
    return cleaned[:120] or None


def _valid_material(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    upper = cleaned.upper().strip(" :.-")
    if upper in BAD_MATERIAL_VALUES:
        return None
    if any(label in upper for label in ["DRAWN BY", "ENGINEER", "SHEET OF", "DWG. NO", "SCALE"]):
        return None
    return cleaned


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_text(data: bytes, suffix: str) -> str:
    if suffix == ".pdf":
        return _extract_pdf_text(data)
    return ""


def _find_material(text: str) -> str | None:
    for pattern in MATERIAL_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1) if match.lastindex else match.group(0)
            value = re.split(r"\s{2,}|(?:\bTHK\b)|(?:\bTHICKNESS\b)", value, flags=re.IGNORECASE)[0]
            material = _valid_material(value)
            if material:
                return material
    return None


def _find_thickness(text: str) -> float | None:
    for pattern in THICKNESS_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def _find_tolerances(text: str) -> tuple[int, float | None]:
    values: list[float] = []
    for match in TOLERANCE_RE.finditer(text):
        raw = match.group(1) or match.group(0)
        try:
            values.append(float(raw.replace("+/-", "").replace("+-", "").strip()))
        except ValueError:
            continue
    return len(values), min(values) if values else None


def analyze_print_bytes(data: bytes, suffix: str) -> PrintFeatures | None:
    try:
        text = _extract_text(data, suffix.lower())
    except Exception:
        text = ""
    if not text.strip():
        return None

    upper = text.upper()
    tolerance_count, tightest_tolerance = _find_tolerances(text)
    gdt_count = sum(upper.count(term) for term in GDT_TERMS)
    datum_count = len(DATUM_RE.findall(text))
    return PrintFeatures(
        material_spec=_find_material(text),
        thickness=_find_thickness(text),
        gdt_callout_count=gdt_count,
        tolerance_count=tolerance_count,
        datum_count=datum_count,
        tightest_tolerance=tightest_tolerance,
        extracted_text=_clean(text) or "",
    )
