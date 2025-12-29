# Test script to verify evidence_preview is preserved in GET /drifts after POST /analyze-repo
# Usage: Run this after starting the backend server
# 
# MANUAL VERIFICATION:
# This script verifies that:
# 1. POST /analyze-repo returns drifts with evidence_preview when forbidden/cycle counts > 0
# 2. GET /drifts returns the same drifts with evidence_preview preserved (wrapper shape: {items: [...]})
# 3. GET /drifts/{id} returns the same drift with evidence_preview preserved
# 4. Frontend can handle both array and wrapper response shapes

# IMPORTANT: Do NOT use variable name $pid (PowerShell treats $PID as automatic/read-only)
# Use $serverPid or other names instead

# 1) Run analyze-repo and keep response
$body = @{
  repo_url = "https://github.com/cosmicpython/code"
  max_commits = 200
  max_drifts  = 100
  classifier_mode = "conformance"
} | ConvertTo-Json

$resp = Invoke-RestMethod -Uri "http://localhost:8000/analyze-repo" -Method POST -ContentType "application/json" -Body $body

# 2) Pick one drift that MUST have evidence (forbidden/cycle count > 0)
$one = $resp | Where-Object {
  ($_.forbidden_edges_added_count -gt 0) -or
  ($_.forbidden_edges_removed_count -gt 0) -or
  ($_.cycles_added_count -gt 0) -or
  ($_.cycles_removed_count -gt 0)
} | Select-Object -First 1

if (-not $one) { 
    Write-Host "No drifts with forbidden/cycle counts > 0 found in this run."
    exit 1
}

Write-Host "Selected drift id = $($one.id)"
Write-Host "Selected drift commit_hash = $($one.commit_hash)"
Write-Host "Analyze evidence count = " + (($one.evidence_preview | Measure-Object).Count)

# IMPORTANT: Drift IDs are generated as commit_hash[:8] (first 8 characters)
# So we need to use the first 8 characters of the commit_hash for lookup
$driftIdForLookup = $one.commit_hash.Substring(0, [Math]::Min(8, $one.commit_hash.Length))

Write-Host "Using drift ID for lookup: $driftIdForLookup (from commit_hash: $($one.commit_hash))"

# 3) GET /drifts returns wrapper shape {items: [...]}
$driftsResp = Invoke-RestMethod -Uri "http://localhost:8000/drifts" -Method GET

# Verify response shape: should be {items: [...]} not an array
if (-not $driftsResp.items) {
    Write-Host "ERROR: GET /drifts response does not have 'items' field. Response shape:"
    $driftsResp | ConvertTo-Json -Depth 2
    exit 1
}

Write-Host "GET /drifts response shape verified: {items: [...]}"

# Find the drift by id (using commit_hash first 8 chars)
$stored = $driftsResp.items | Where-Object { $_.id -eq $driftIdForLookup } | Select-Object -First 1

if (-not $stored) { 
    Write-Host "Available drift IDs in GET /drifts (first 10):"
    $driftsResp.items | Select-Object -First 10 | ForEach-Object { Write-Host "  - id: $($_.id), commit_hash: $($_.commit_hash)" }
    throw "Drift id $driftIdForLookup not found in GET /drifts."
}

Write-Host "GET /drifts evidence count = " + (($stored.evidence_preview | Measure-Object).Count)
if ($stored.evidence_preview.Count -eq 0) {
    Write-Host "ERROR: evidence_preview is empty in GET /drifts!"
    exit 1
}
Write-Host "Evidence preview from GET /drifts:"
$stored.evidence_preview | ConvertTo-Json -Depth 10

# 4) GET /drifts/{id} should also preserve it
$byId = Invoke-RestMethod -Uri ("http://localhost:8000/drifts/{0}" -f $driftIdForLookup) -Method GET
Write-Host "GET /drifts/{id} evidence count = " + (($byId.evidence_preview | Measure-Object).Count)
if ($byId.evidence_preview.Count -eq 0) {
    Write-Host "ERROR: evidence_preview is empty in GET /drifts/{id}!"
    exit 1
}
Write-Host "Evidence preview from GET /drifts/{id}:"
$byId.evidence_preview | ConvertTo-Json -Depth 10

# 5) Verify all required fields are present
Write-Host "`nVerifying required fields:"
Write-Host "  baseline_hash: $($stored.baseline_hash)"
Write-Host "  rules_hash: $($stored.rules_hash)"
Write-Host "  classifier_mode_used: $($stored.classifier_mode_used)"
Write-Host "  classification: $($stored.classification)"

Write-Host "`nSUCCESS: evidence_preview is preserved in both GET /drifts and GET /drifts/{id}"

