from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from .database import Base, UPLOAD_DIR, engine, get_db
from .models import AwardedJob, JobFile
from .schemas import AwardedJobRead, QuoteSearchInput, QuoteSearchResult, SimilarJob
from .similarity import score_job, suggested_range
from .step_features import StepFeatures, extract_step_features


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".step", ".stp"}

Base.metadata.create_all(bind=engine)


def _ensure_sqlite_columns():
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns("awarded_jobs")}
    missing = [
        (column.name, column.type.compile(engine.dialect))
        for column in AwardedJob.__table__.columns
        if column.name not in existing
    ]
    if not missing:
        return
    with engine.begin() as connection:
        for name, sql_type in missing:
            connection.execute(text(f"ALTER TABLE awarded_jobs ADD COLUMN {name} {sql_type}"))


_ensure_sqlite_columns()

app = FastAPI(title="Stamping Tool AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _apply_step_features(target: AwardedJob | QuoteSearchInput, features: StepFeatures | None) -> None:
    if not features:
        return
    target.step_bbox_length = features.bbox_length
    target.step_bbox_width = features.bbox_width
    target.step_bbox_height = features.bbox_height
    target.step_bbox_volume = features.bbox_volume
    target.step_bbox_diagonal = features.bbox_diagonal
    target.step_point_count = features.point_count


def _save_upload(job: AwardedJob, upload: UploadFile, db: Session) -> JobFile:
    original_name = upload.filename or "upload"
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or original_name}")

    job_dir = UPLOAD_DIR / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    stored_path = job_dir / stored_name
    data = upload.file.read()
    stored_path.write_bytes(data)
    if suffix in {".step", ".stp"}:
        _apply_step_features(job, extract_step_features(data))

    file_record = JobFile(
        job_id=job.id,
        original_filename=original_name,
        stored_filename=f"{job.id}/{stored_name}",
        content_type=upload.content_type,
        file_size=len(data),
    )
    db.add(file_record)
    return file_record


def _score_jobs(input_data: QuoteSearchInput, db: Session) -> QuoteSearchResult:
    jobs = db.query(AwardedJob).all()
    scored = sorted(
        ((job, *score_job(input_data, job)) for job in jobs),
        key=lambda item: item[1],
        reverse=True,
    )
    top_matches = scored[:10]
    return QuoteSearchResult(
        results=[
            SimilarJob(job=AwardedJobRead.model_validate(job), score=score, breakdown=breakdown)
            for job, score, breakdown in top_matches
        ],
        suggested_quote_range=suggested_range(top_matches),
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/jobs", response_model=list[AwardedJobRead])
def list_jobs(search: str | None = None, db: Session = Depends(get_db)):
    query = db.query(AwardedJob)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                AwardedJob.customer_name.ilike(pattern),
                AwardedJob.customer_type.ilike(pattern),
                AwardedJob.industry.ilike(pattern),
                AwardedJob.part_number.ilike(pattern),
                AwardedJob.part_description.ilike(pattern),
                AwardedJob.material.ilike(pattern),
                AwardedJob.die_type.ilike(pattern),
                AwardedJob.press_size.ilike(pattern),
                AwardedJob.notes.ilike(pattern),
                AwardedJob.lessons_learned.ilike(pattern),
            )
        )
    return query.order_by(AwardedJob.created_at.desc()).all()


@app.get("/api/jobs/{job_id}", response_model=AwardedJobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(AwardedJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs", response_model=AwardedJobRead, status_code=201)
async def create_job(
    customer_name: str = Form(...),
    part_number: str = Form(...),
    customer_type: str | None = Form(None),
    industry: str | None = Form(None),
    part_description: str | None = Form(None),
    material: str | None = Form(None),
    material_thickness: str | None = Form(None),
    annual_volume: str | None = Form(None),
    program_life: str | None = Form(None),
    die_type: str | None = Form(None),
    number_of_stations: str | None = Form(None),
    die_length: str | None = Form(None),
    die_width: str | None = Form(None),
    die_height: str | None = Form(None),
    die_weight: str | None = Form(None),
    press_size: str | None = Form(None),
    quoted_price: str | None = Form(None),
    awarded_price: str | None = Form(None),
    actual_tool_build_hours: str | None = Form(None),
    design_hours: str | None = Form(None),
    cam_hours: str | None = Form(None),
    cnc_hours: str | None = Form(None),
    wire_hours: str | None = Form(None),
    bench_hours: str | None = Form(None),
    tryout_hours: str | None = Form(None),
    outsourced_cost: str | None = Form(None),
    material_cost: str | None = Form(None),
    profit_margin: str | None = Form(None),
    notes: str | None = Form(None),
    lessons_learned: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    job = AwardedJob(
        customer_name=customer_name,
        customer_type=customer_type,
        industry=industry,
        part_number=part_number,
        part_description=part_description,
        material=material,
        material_thickness=_optional_float(material_thickness),
        annual_volume=_optional_int(annual_volume),
        program_life=_optional_float(program_life),
        die_type=die_type,
        number_of_stations=_optional_int(number_of_stations),
        die_length=_optional_float(die_length),
        die_width=_optional_float(die_width),
        die_height=_optional_float(die_height),
        die_weight=_optional_float(die_weight),
        press_size=press_size,
        quoted_price=_optional_float(quoted_price),
        awarded_price=_optional_float(awarded_price),
        actual_tool_build_hours=_optional_float(actual_tool_build_hours),
        design_hours=_optional_float(design_hours),
        cam_hours=_optional_float(cam_hours),
        cnc_hours=_optional_float(cnc_hours),
        wire_hours=_optional_float(wire_hours),
        bench_hours=_optional_float(bench_hours),
        tryout_hours=_optional_float(tryout_hours),
        outsourced_cost=_optional_float(outsourced_cost),
        material_cost=_optional_float(material_cost),
        profit_margin=_optional_float(profit_margin),
        notes=notes,
        lessons_learned=lessons_learned,
    )
    db.add(job)
    db.flush()

    for upload in files:
        if upload.filename:
            _save_upload(job, upload, db)

    db.commit()
    db.refresh(job)
    return job


@app.post("/api/quote-search", response_model=QuoteSearchResult)
def quote_search(input_data: QuoteSearchInput, db: Session = Depends(get_db)):
    return _score_jobs(input_data, db)


@app.post("/api/quote-search/upload", response_model=QuoteSearchResult)
async def quote_search_upload(
    customer_type: str | None = Form(None),
    industry: str | None = Form(None),
    material: str | None = Form(None),
    material_thickness: str | None = Form(None),
    annual_volume: str | None = Form(None),
    actual_tool_build_hours: str | None = Form(None),
    die_type: str | None = Form(None),
    number_of_stations: str | None = Form(None),
    die_length: str | None = Form(None),
    die_width: str | None = Form(None),
    die_height: str | None = Form(None),
    notes: str | None = Form(None),
    lessons_learned: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    input_data = QuoteSearchInput(
        customer_type=customer_type,
        industry=industry,
        material=material,
        material_thickness=_optional_float(material_thickness),
        annual_volume=_optional_int(annual_volume),
        actual_tool_build_hours=_optional_float(actual_tool_build_hours),
        die_type=die_type,
        number_of_stations=_optional_int(number_of_stations),
        die_length=_optional_float(die_length),
        die_width=_optional_float(die_width),
        die_height=_optional_float(die_height),
        notes=notes,
        lessons_learned=lessons_learned,
    )

    for upload in files:
        if not upload.filename:
            continue
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or upload.filename}")
        data = await upload.read()
        if suffix in {".step", ".stp"}:
            _apply_step_features(input_data, extract_step_features(data))

    return _score_jobs(input_data, db)
