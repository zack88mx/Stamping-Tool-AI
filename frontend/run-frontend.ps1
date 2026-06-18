$ErrorActionPreference = "Stop"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm was not found. Install Node.js LTS from https://nodejs.org, then reopen PowerShell and rerun this script."
}

npm install
npm run dev
