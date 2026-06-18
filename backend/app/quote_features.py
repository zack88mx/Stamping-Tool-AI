import io
import re
from dataclasses import dataclass

from pypdf import PdfReader

from .print_features import _find_material, _find_thickness


NUMBER = r"([-+]?\$?\s*(?:\d[\d,]*(?:\.\d+)?|\.\d+))"
MONEY = r"\$?\s*([0-9][0-9,]*(?:\.\d+)?)"


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text(extraction_mode="layout") or "")
        except TypeError:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _clean_number(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def _search_number(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _clean_number(match.group(1))
    return None


def _search_int(patterns: list[str], text: str) -> int | None:
    value = _search_number(patterns, text)
    return int(round(value)) if value is not None else None


def _search_text(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            cleaned = " ".join(match.group(1).replace("\n", " ").split())
            return cleaned[:120] or None
    return None


def _find_quote_table_thickness(text: str) -> float | None:
    match = re.search(rf"\bThickness\s+Blank\s+Size\s+{NUMBER}\s*(?:\"|IN|INCHES)?", text, re.IGNORECASE)
    if match:
        return _clean_number(match.group(1))
    return None


def _apply_first_tooling_row(fields: dict[str, str | int | float], text: str) -> None:
    part_match = re.search(r"^\s*([0-9][A-Z0-9._/-]{3,})\s+Type:\s*([^\n]+)", text, re.IGNORECASE | re.MULTILINE)
    if part_match:
        fields.setdefault("part_number", part_match.group(1).strip())
        die_type = " ".join(part_match.group(2).split())
        die_type = re.split(r"\bPress\b|\bTooling\b", die_type, flags=re.IGNORECASE)[0].strip()
        if die_type:
            fields.setdefault("die_type", die_type)

    press_match = re.search(r"\bPress\s+([A-Z](?:\s+or\s+[A-Z])?)\b", text, re.IGNORECASE)
    if press_match:
        fields.setdefault("press_size", press_match.group(1).strip())

    station_match = re.search(r"\b([0-9]+)\s*#?\s*Stations?\s*:\s*Die\s*Size", text, re.IGNORECASE)
    if station_match:
        fields.setdefault("number_of_stations", int(station_match.group(1)))

    die_match = re.search(
        rf"\bDie\s*Size\s*:\s*{NUMBER}\s*(?:\"|IN|INCHES)?\s*[Xx×]\s*{NUMBER}\s*(?:\"|IN|INCHES)?",
        text,
        re.IGNORECASE,
    )
    if die_match:
        fields.setdefault("die_length", _clean_number(die_match.group(1)))
        fields.setdefault("die_width", _clean_number(die_match.group(2)))

    price_match = re.search(rf"\bTooling\s*:\s*.*?\$\s*([0-9][0-9,]*(?:\.\d+)?)", text, re.IGNORECASE | re.DOTALL)
    if price_match:
        fields["quoted_price"] = _clean_number(price_match.group(1))


@dataclass(frozen=True)
class QuoteFeatures:
    fields: dict[str, str | int | float]
    extracted_text: str


def analyze_quote_bytes(data: bytes, suffix: str) -> QuoteFeatures | None:
    if suffix.lower() != ".pdf":
        return None
    try:
        text = _extract_pdf_text(data)
    except Exception:
        text = ""
    if not text.strip():
        return None

    fields: dict[str, str | int | float] = {}
    material = _find_material(text)
    thickness = _find_thickness(text)
    if material:
        fields["material"] = material
    table_thickness = _find_quote_table_thickness(text)
    if table_thickness is not None:
        fields["material_thickness"] = table_thickness
    elif thickness is not None:
        fields["material_thickness"] = thickness

    text_patterns = {
        "customer_name": [r"\bCUSTOMER\s*[:\-]\s*([A-Z0-9 &.,'/-]{2,80})"],
        "part_number": [r"\b(?:PART\s*(?:NO\.?|NUMBER)|P/N)\s*[:\-]\s*([A-Z0-9._/-]{2,60})"],
        "part_description": [r"\b(?:PART\s*)?DESCRIPTION\s*[:\-]\s*([A-Z0-9 &.,'/-]{2,120})"],
        "die_type": [r"\b(?:DIE|TOOL)\s*TYPE\s*[:\-]\s*([A-Z0-9 &.,'/-]{2,80})"],
        "press_size": [r"\bPRESS\s*(?:SIZE|TONNAGE)?\s*[:\-]\s*([A-Z0-9 &.,'/-]{2,80})"],
    }
    for name, patterns in text_patterns.items():
        value = _search_text(patterns, text)
        if value:
            fields[name] = value

    numeric_patterns = {
        "die_length": [
            rf"\b(?:DIE|TOOL(?:ING)?)\s*(?:LENGTH|L)\s*[:=\-]\s*{NUMBER}",
            rf"\bLENGTH\s*[:=\-]\s*{NUMBER}",
        ],
        "die_width": [
            rf"\b(?:DIE|TOOL(?:ING)?)\s*(?:WIDTH|W)\s*[:=\-]\s*{NUMBER}",
            rf"\bWIDTH\s*[:=\-]\s*{NUMBER}",
        ],
        "die_height": [
            rf"\b(?:DIE|TOOL(?:ING)?)\s*(?:HEIGHT|H)\s*[:=\-]\s*{NUMBER}",
            rf"\bHEIGHT\s*[:=\-]\s*{NUMBER}",
        ],
        "die_weight": [rf"\b(?:DIE|TOOL(?:ING)?)\s*WEIGHT\s*[:=\-]\s*{NUMBER}"],
        "quoted_price": [
            rf"\bQUOTED\s*PRICE\s*[:=\-]\s*{MONEY}",
            rf"\bQUOTE\s*PRICE\s*[:=\-]\s*{MONEY}",
            rf"\bTOOL(?:ING)?\s*(?:PRICE|COST|TOTAL)\s*[:=\-]\s*{MONEY}",
        ],
        "awarded_price": [rf"\bAWARDED\s*(?:PRICE|COST)?\s*[:=\-]\s*{MONEY}"],
        "actual_tool_build_hours": [rf"\b(?:ACTUAL\s*)?(?:TOOL\s*)?BUILD\s*HOURS\s*[:=\-]\s*{NUMBER}"],
        "design_hours": [rf"\bDESIGN\s*HOURS\s*[:=\-]\s*{NUMBER}"],
        "cam_hours": [rf"\bCAM\s*HOURS\s*[:=\-]\s*{NUMBER}"],
        "cnc_hours": [rf"\bCNC\s*HOURS\s*[:=\-]\s*{NUMBER}"],
        "wire_hours": [rf"\bWIRE\s*HOURS\s*[:=\-]\s*{NUMBER}"],
        "bench_hours": [rf"\bBENCH\s*HOURS\s*[:=\-]\s*{NUMBER}"],
        "tryout_hours": [rf"\bTRY(?:OUT)?\s*HOURS\s*[:=\-]\s*{NUMBER}"],
        "outsourced_cost": [rf"\bOUTSOURCED\s*(?:COST)?\s*[:=\-]\s*{MONEY}"],
        "material_cost": [rf"\bMATERIAL\s*COST\s*[:=\-]\s*{MONEY}"],
        "profit_margin": [rf"\b(?:PROFIT\s*)?MARGIN\s*[:=\-]\s*{NUMBER}\s*%?"],
        "annual_volume": [rf"\b(?:ANNUAL\s*)?VOLUME\s*[:=\-]\s*{NUMBER}"],
        "program_life": [rf"\bPROGRAM\s*LIFE\s*[:=\-]\s*{NUMBER}"],
    }
    for name, patterns in numeric_patterns.items():
        value = _search_number(patterns, text)
        if value is not None:
            fields[name] = value

    stations = _search_int([rf"\b(?:NUMBER\s*OF\s*)?STATIONS\s*[:=\-]\s*{NUMBER}"], text)
    if stations is not None:
        fields["number_of_stations"] = stations

    size_match = re.search(
        rf"\b(?:DIE|TOOL(?:ING)?)\s*(?:SIZE|DIMENSIONS?)\s*[:=\-]?\s*{NUMBER}\s*[Xx×]\s*{NUMBER}\s*[Xx×]\s*{NUMBER}",
        text,
        re.IGNORECASE,
    )
    if size_match:
        fields.setdefault("die_length", _clean_number(size_match.group(1)))
        fields.setdefault("die_width", _clean_number(size_match.group(2)))
        fields.setdefault("die_height", _clean_number(size_match.group(3)))

    two_dim_size_match = re.search(
        rf"\b(?:DIE|TOOL(?:ING)?)\s*(?:SIZE|DIMENSIONS?)\s*[:=\-]?\s*{NUMBER}\s*(?:\"|IN|INCHES)?\s*[Xx×]\s*{NUMBER}",
        text,
        re.IGNORECASE,
    )
    if two_dim_size_match:
        fields.setdefault("die_length", _clean_number(two_dim_size_match.group(1)))
        fields.setdefault("die_width", _clean_number(two_dim_size_match.group(2)))

    _apply_first_tooling_row(fields, text)

    return QuoteFeatures(fields={k: v for k, v in fields.items() if v is not None}, extracted_text=text[:2000])
