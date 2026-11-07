# Udyam OneFlow on Windows. Usage: .\run.ps1 [setup|test|reports|serve|dev]
param([string]$cmd = "serve")
$env:PYTHONIOENCODING = "utf-8"
$root = $PSScriptRoot
switch ($cmd) {
  "setup"   { python -m pip install -r "$root\backend\requirements.txt"; Push-Location "$root\frontend"; npm install; Pop-Location }
  "test"    { Push-Location "$root\backend"; python -m pytest -q; Pop-Location }
  "reports" { python "$root\scripts\analyze_leads.py"; python "$root\scripts\run_kyc_batch.py";
              python "$root\scripts\train_propensity.py" --data "$root\backend\app\data" --out "$root\reports" --models "$root\models";
              python "$root\scripts\simulate.py" }
  "dev"     { Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python -m uvicorn app.main:app --reload --port 8000";
              Push-Location "$root\frontend"; npm run dev; Pop-Location }
  default   { Push-Location "$root\frontend"; npm run build; Pop-Location
              python "$root\scripts\seed.py"
              Write-Host "Open http://127.0.0.1:8000  (demo controls: http://127.0.0.1:8000/?demo=1)"
              Push-Location "$root\backend"; python -m uvicorn app.main:app --port 8000; Pop-Location }
}
