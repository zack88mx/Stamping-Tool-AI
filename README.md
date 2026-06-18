# Stamping Tool AI

A local MVP for storing awarded stamped-metal jobs and using them to quote similar parts faster.

## Stack

- FastAPI backend
- SQLite database
- React + Vite frontend
- Local file storage in `backend/uploads`
- Weighted similarity scoring engine

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

## Awarded job fields

The MVP captures customer, industry, part, material, volume/program, die size, press, quoted/awarded pricing, detailed build-hour buckets, costs, margin, notes, lessons learned, and uploaded PDF/image/STEP/STP files.

## Similarity weights

- Material/material thickness: 20%
- Part size/die size: 20%
- Number of stations: 20%
- Die type: 15%
- Customer type: 10%
- Actual tool build hours similarity: 10%
- Notes/lessons learned complexity: 5%

The suggested quote range uses the top matches with awarded prices and calculates a weighted center plus a practical spread.
