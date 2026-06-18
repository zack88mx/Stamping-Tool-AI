import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from .config import STORAGE_BACKEND, UPLOAD_DIR
from .database import Base, engine, get_db
from .models import AwardedJob, JobFile
from .print_features import PrintFeatures, analyze_print_bytes
from .schemas import AwardedJobRead, PrintAnalysisResult, QuoteSearchInput, QuoteSearchResult, SimilarJob
from .similarity import score_job, suggested_range
from .step_features import StepFeatures, extract_step_features
from .storage import storage


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
if STORAGE_BACKEND == "local":
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


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _apply_print_features(target: AwardedJob | QuoteSearchInput, features: PrintFeatures | None) -> None:
    if not features:
        return
    target.print_material_spec = features.material_spec
    target.print_thickness = features.thickness
    target.print_gdt_callout_count = features.gdt_callout_count
    target.print_tolerance_count = features.tolerance_count
    target.print_datum_count = features.datum_count
    target.print_tightest_tolerance = features.tightest_tolerance
    target.print_feature_text = features.extracted_text
    if features.material_spec and not target.material:
        target.material = features.material_spec
    if features.thickness is not None and target.material_thickness is None:
        target.material_thickness = features.thickness


def _apply_file_features(target: AwardedJob | QuoteSearchInput, data: bytes, suffix: str) -> None:
    file_hash = _hash_bytes(data)
    if suffix in {".step", ".stp"}:
        target.step_file_hash = file_hash
        _apply_step_features(target, extract_step_features(data))
    if suffix in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        target.print_file_hash = file_hash
        _apply_print_features(target, analyze_print_bytes(data, suffix))


def _analysis_result(features: PrintFeatures | None) -> PrintAnalysisResult:
    if not features:
        return PrintAnalysisResult(
            material=None,
            material_thickness=None,
            gdt_callout_count=0,
            tolerance_count=0,
            datum_count=0,
            tightest_tolerance=None,
            extracted_text="",
        )
    return PrintAnalysisResult(
        material=features.material_spec,
        material_thickness=features.thickness,
        gdt_callout_count=features.gdt_callout_count,
        tolerance_count=features.tolerance_count,
        datum_count=features.datum_count,
        tightest_tolerance=features.tightest_tolerance,
        extracted_text=features.extracted_text,
    )


def _save_upload(job: AwardedJob, upload: UploadFile, db: Session) -> JobFile:
    original_name = upload.filename or "upload"
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or original_name}")

    stored_name = f"{uuid4().hex}{suffix}"
    data = upload.file.read()
    stored_filename = storage.save(f"{job.id}/{stored_name}", data, upload.content_type)
    _apply_file_features(job, data, suffix)

    file_record = JobFile(
        job_id=job.id,
        original_filename=original_name,
        stored_filename=stored_filename,
        content_type=upload.content_type,
        file_size=len(data),
    )
    db.add(file_record)
    return file_record


def _reprocess_job_files(job: AwardedJob) -> None:
    for file_record in job.files:
        suffix = Path(file_record.original_filename or file_record.stored_filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            continue
        data = storage.read(file_record.stored_filename)
        _apply_file_features(job, data, suffix)


def _job_read(job: AwardedJob, request: Request | None = None) -> AwardedJobRead:
    payload = AwardedJobRead.model_validate(job)
    for file in payload.files:
        url = storage.url_for(file.stored_filename)
        if request and url.startswith("/"):
            url = str(request.url_for("uploads", path=file.stored_filename))
        file.url = url
    return payload


def _score_jobs(input_data: QuoteSearchInput, db: Session, request: Request | None = None) -> QuoteSearchResult:
    jobs = db.query(AwardedJob).all()
    scored = sorted(
        ((job, *score_job(input_data, job)) for job in jobs),
        key=lambda item: item[1],
        reverse=True,
    )
    top_matches = scored[:10]
    return QuoteSearchResult(
        results=[
            SimilarJob(job=_job_read(job, request), score=score, breakdown=breakdown)
            for job, score, breakdown in top_matches
        ],
        suggested_quote_range=suggested_range(top_matches),
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/jobs", response_model=list[AwardedJobRead])
def list_jobs(request: Request, search: str | None = None, db: Session = Depends(get_db)):
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
    return [_job_read(job, request) for job in query.order_by(AwardedJob.created_at.desc()).all()]


@app.get("/api/jobs/{job_id}", response_model=AwardedJobRead)
def get_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.get(AwardedJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_read(job, request)


@app.post("/api/prints/analyze", response_model=PrintAnalysisResult)
async def analyze_print(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or file.filename}")
    data = await file.read()
    return _analysis_result(analyze_print_bytes(data, suffix))


@app.post("/api/jobs/{job_id}/reprocess", response_model=AwardedJobRead)
def reprocess_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.get(AwardedJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _reprocess_job_files(job)
    db.commit()
    db.refresh(job)
    return _job_read(job, request)


@app.post("/api/jobs", response_model=AwardedJobRead, status_code=201)
async def create_job(
    request: Request,
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
    return _job_read(job, request)


@app.post("/api/quote-search", response_model=QuoteSearchResult)
def quote_search(input_data: QuoteSearchInput, request: Request, db: Session = Depends(get_db)):
    return _score_jobs(input_data, db, request)


@app.post("/api/quote-search/upload", response_model=QuoteSearchResult)
async def quote_search_upload(
    request: Request,
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
        _apply_file_features(input_data, data, suffix)

    return _score_jobs(input_data, db, request)
