from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class AwardedJob(Base):
    __tablename__ = "awarded_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), index=True)
    customer_type: Mapped[str | None] = mapped_column(String(120), index=True)
    industry: Mapped[str | None] = mapped_column(String(120), index=True)
    part_number: Mapped[str] = mapped_column(String(120), index=True)
    part_description: Mapped[str | None] = mapped_column(String(255))
    material: Mapped[str | None] = mapped_column(String(120), index=True)
    material_thickness: Mapped[float | None] = mapped_column(Float)
    annual_volume: Mapped[int | None] = mapped_column(Integer)
    program_life: Mapped[float | None] = mapped_column(Float)
    die_type: Mapped[str | None] = mapped_column(String(120), index=True)
    number_of_stations: Mapped[int | None] = mapped_column(Integer)
    die_length: Mapped[float | None] = mapped_column(Float)
    die_width: Mapped[float | None] = mapped_column(Float)
    die_height: Mapped[float | None] = mapped_column(Float)
    die_weight: Mapped[float | None] = mapped_column(Float)
    press_size: Mapped[str | None] = mapped_column(String(120))
    quoted_price: Mapped[float | None] = mapped_column(Float)
    awarded_price: Mapped[float | None] = mapped_column(Float)
    actual_tool_build_hours: Mapped[float | None] = mapped_column(Float)
    design_hours: Mapped[float | None] = mapped_column(Float)
    cam_hours: Mapped[float | None] = mapped_column(Float)
    cnc_hours: Mapped[float | None] = mapped_column(Float)
    wire_hours: Mapped[float | None] = mapped_column(Float)
    bench_hours: Mapped[float | None] = mapped_column(Float)
    tryout_hours: Mapped[float | None] = mapped_column(Float)
    outsourced_cost: Mapped[float | None] = mapped_column(Float)
    material_cost: Mapped[float | None] = mapped_column(Float)
    profit_margin: Mapped[float | None] = mapped_column(Float)
    step_bbox_length: Mapped[float | None] = mapped_column(Float)
    step_bbox_width: Mapped[float | None] = mapped_column(Float)
    step_bbox_height: Mapped[float | None] = mapped_column(Float)
    step_bbox_volume: Mapped[float | None] = mapped_column(Float)
    step_bbox_diagonal: Mapped[float | None] = mapped_column(Float)
    step_point_count: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    lessons_learned: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    files: Mapped[list["JobFile"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class JobFile(Base):
    __tablename__ = "job_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("awarded_jobs.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(120))
    file_size: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[AwardedJob] = relationship(back_populates="files")
