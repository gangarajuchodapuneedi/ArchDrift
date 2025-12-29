# Hard restart script for ArchDrift backend
Write-Host "Stopping any running uvicorn processes..."
Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*uvicorn*" } | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Clearing Python cache..."
Get-ChildItem -Path . -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "Starting server..."
.\.venv\Scripts\Activate
python -m uvicorn main:app --reload --port 8000

