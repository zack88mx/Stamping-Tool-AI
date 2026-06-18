# Stamping Tool AI

A local MVP for storing awarded stamped-metal jobs and using them to quote similar parts faster.

## Stack

- FastAPI backend
- SQLite database
- React + Vite frontend
- Local file storage in `backend/uploads`
- Weighted similarity scoring engine
- STEP/STP 3D bounding-box feature extraction
- PDF print text extraction for material, thickness, tolerances, and GD&T-like callouts

## Run locally

Open two terminals.

Backend:

```powershell
cd work/stamping-tool-ai/backend
.\run-backend.ps1
```

Frontend:

```powershell
cd work/stamping-tool-ai/frontend
.\run-frontend.ps1
```

Then open `http://127.0.0.1:5173`.

If `npm` is not found, install Node.js LTS first, then reopen PowerShell.

## Storage

SQLite is the default database. Local development stores the database at `backend/app.db` and uploaded files at `backend/uploads`.

For deployment, set `DATA_DIR` to a persistent disk path so SQLite survives restarts:

```bash
DATA_DIR=/var/data/stamping-tool-ai
```

The app supports local file storage by default:

```bash
STORAGE_BACKEND=local
UPLOAD_DIR=/var/data/stamping-tool-ai/uploads
```

For AWS S3 or Cloudflare R2, use the S3-compatible storage backend:

```bash
STORAGE_BACKEND=s3
S3_BUCKET=your-bucket-name
S3_REGION=auto
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_PUBLIC_BASE_URL=https://files.your-domain.com
S3_KEY_PREFIX=uploads
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

For AWS S3, omit `S3_ENDPOINT_URL` and set `S3_REGION` to your AWS region. If `S3_PUBLIC_BASE_URL` is not set, the backend returns temporary presigned download URLs.

## Awarded job fields

The MVP captures customer, industry, part, material, volume/program, die size, press, quoted/awarded pricing, detailed build-hour buckets, costs, margin, notes, lessons learned, and uploaded PDF/image/STEP/STP files.

STEP/STP files are parsed for `CARTESIAN_POINT` coordinates. The app stores a simple 3D bounding box, diagonal, volume, and point count for awarded jobs, then uses those features when a new quote search includes a STEP/STP file.

Text-based PDF prints are analyzed for material specification, thickness, tolerance count, datum count, tightest tolerance, and common GD&T terms such as position, profile, flatness, parallelism, perpendicularity, and runout. When a readable print is selected in the UI, material and material thickness are auto-filled if the fields are still blank.

Scanned image prints can still be uploaded and stored. OCR is not bundled in this MVP, so images need a future OCR service or local Tesseract setup before their print text can be extracted.

## Similarity weights

- Material/material thickness: 20%
- Part size/die size/STEP-STP 3D size: 20%
- Number of stations: 20%
- Die type: 15%
- Customer type: 10%
- Actual tool build hours similarity: 10%
- Notes/lessons learned/GD&T print complexity: 5%

The suggested quote range uses the top matches with awarded prices and calculates a weighted center plus a practical spread.
