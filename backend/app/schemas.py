from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    stored_filename: str
    content_type: str | None
    file_size: int
    uploaded_at: datetime


class AwardedJobBase(BaseModel):
    customer_name: str
    customer_type: str | None = None
    industry: str | None = None
    part_number: str
    part_description: str | None = None
    material: str | None = None
    material_thickness: float | None = None
    annual_volume: int | None = None
    program_life: float | None = None
    die_type: str | None = None
    number_of_stations: int | None = None
    die_length: float | None = None
    die_width: float | None = None
    die_height: float | None = None
    die_weight: float | None = None
    press_size: str | None = None
    quoted_price: float | None = None
    awarded_price: float | None = None
    actual_tool_build_hours: float | None = None
    design_hours: float | None = None
    cam_hours: float | None = None
    cnc_hours: float | None = None
    wire_hours: float | None = None
    bench_hours: float | None = None
    tryout_hours: float | None = None
    outsourced_cost: float | None = None
    material_cost: float | None = None
    profit_margin: float | None = None
    step_bbox_length: float | None = None
    step_bbox_width: float | None = None
    step_bbox_height: float | None = None
    step_bbox_volume: float | None = None
    step_bbox_diagonal: float | None = None
    step_point_count: int | None = None
    notes: str | None = None
    lessons_learned: str | None = None


class AwardedJobCreate(AwardedJobBase):
    pass


class AwardedJobRead(AwardedJobBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    files: list[JobFileRead] = []


class QuoteSearchInput(BaseModel):
    customer_type: str | None = None
    industry: str | None = None
    material: str | None = None
    material_thickness: float | None = None
    annual_volume: int | None = None
    actual_tool_build_hours: float | None = None
    die_type: str | None = None
    number_of_stations: int | None = None
    die_length: float | None = None
    die_width: float | None = None
    die_height: float | None = None
    step_bbox_length: float | None = None
    step_bbox_width: float | None = None
    step_bbox_height: float | None = None
    step_bbox_volume: float | None = None
    step_bbox_diagonal: float | None = None
    step_point_count: int | None = None
    notes: str | None = None
    lessons_learned: str | None = None


class SimilarJob(BaseModel):
    job: AwardedJobRead
    score: float = Field(ge=0, le=100)
    breakdown: dict[str, float]


class QuoteRange(BaseModel):
    low: float | None
    high: float | None
    average: float | None
    basis_count: int


class QuoteSearchResult(BaseModel):
    results: list[SimilarJob]
    suggested_quote_range: QuoteRange
