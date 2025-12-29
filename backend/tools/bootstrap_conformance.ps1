<#
.SYNOPSIS
    Bootstrap script for ArchDrift conformance mode - automates baseline setup and analysis.

.DESCRIPTION
    This script automates the full conformance mode workflow:
    - Checks backend health
    - Discovers or uses a repository URL
    - Clones/opens repo and gets local path
    - Generates baseline if missing
    - Auto-approves baseline (optional)
    - Runs analysis
    - Displays results in a compact table

.PARAMETER Port
    Backend server port (default: 8000)

.PARAMETER RepoUrl
    Optional repository URL. If not provided, script will try to discover from existing drifts or use default.

.PARAMETER MaxCommits
    Maximum number of commits to analyze (default: 20)

.PARAMETER MaxDrifts
    Maximum number of drifts to return (default: 5)

.PARAMETER ApprovedBy
    Name/email for baseline approval (default: "local-dev")

.PARAMETER AutoApprove
    Automatically approve baseline after generation (default: $true)

.EXAMPLE
    .\bootstrap_conformance.ps1 -Port 8000

.EXAMPLE
    .\bootstrap_conformance.ps1 -RepoUrl "https://github.com/user/repo" -Port 8000

.EXAMPLE
    .\bootstrap_conformance.ps1 -MaxCommits 30 -MaxDrifts 10 -Port 8000
#>

param(
  [int]$Port = 8000,
  [string]$RepoUrl = "",
  [int]$MaxCommits = 20,
  [int]$MaxDrifts = 5,
  [string]$ApprovedBy = "local-dev",
  [switch]$NoAutoApprove
)

$ErrorActionPreference = "Stop"
$baseUrl = "http://127.0.0.1:$Port"

function Invoke-Api {
  param([string]$Method, [string]$Path, [object]$Body = $null)
  $uri = "$baseUrl$Path"
  if ($null -ne $Body) {
    $json = $Body | ConvertTo-Json -Depth 10
    return Invoke-RestMethod -Method $Method -Uri $uri -ContentType "application/json" -Body $json
  } else {
    return Invoke-RestMethod -Method $Method -Uri $uri
  }
}

Write-Host "STEP 0: Health"
$health = Invoke-Api GET "/health"
if ($health.status -ne "healthy") { throw "Backend not healthy: $($health.status)" }
Write-Host "OK: backend healthy at $baseUrl"

Write-Host "STEP 1: Pick RepoUrl"
if (-not $RepoUrl) {
  $drifts = Invoke-Api GET "/drifts"
  if ($drifts.items -and $drifts.items.Count -gt 0 -and $drifts.items[0].repo_url) {
    $RepoUrl = $drifts.items[0].repo_url
  } else {
    $RepoUrl = "https://github.com/nestjs/typescript-starter"
  }
}
Write-Host "RepoUrl: $RepoUrl"

Write-Host "STEP 2: /debug/list-commits (gets local repo_path)"
$commits = Invoke-Api POST "/debug/list-commits" @{ repo_url = $RepoUrl; max_commits = 1 }
$repoPath = $commits.repo_path
if (-not $repoPath) { throw "debug/list-commits did not return repo_path" }
Write-Host "repo_path: $repoPath"

Write-Host "STEP 3: baseline status"
$encoded = [System.Uri]::EscapeDataString($repoPath)
$exists = $false
try {
  $status = Invoke-Api GET "/baseline/status?repo_path=$encoded"
  $exists = [bool]$status.exists
} catch {
  $exists = $false
}
Write-Host "baseline exists: $exists"

if (-not $exists) {
  Write-Host "STEP 4: baseline generate"
  $gen = Invoke-Api POST "/baseline/generate" @{ repo_path = $repoPath }
  Write-Host "baseline_dir: $($gen.baseline_dir)"
  Write-Host "baseline_hash: $($gen.baseline_hash_sha256)"
}

if (-not $NoAutoApprove) {
  Write-Host "STEP 5: baseline approve"
  $approveBody = @{
    repo_path = $repoPath
    approved_by = $ApprovedBy
    approval_note = "bootstrap conformance"
    exceptions = @()
  }
  try {
    $ap = Invoke-Api POST "/baseline/approve" $approveBody
  } catch {
    # Try once more after generating baseline
    $null = Invoke-Api POST "/baseline/generate" @{ repo_path = $repoPath }
    $ap = Invoke-Api POST "/baseline/approve" $approveBody
  }
  Write-Host "approved_by: $($ap.approved_by)"
  Write-Host "approved_at: $($ap.approved_at)"
} else {
  Write-Host "STEP 5: Auto-approve skipped"
}

Write-Host "STEP 6: analyze"
$resp = Invoke-Api POST "/analyze-repo" @{ repo_url = $RepoUrl; max_commits = $MaxCommits; max_drifts = $MaxDrifts }
Write-Host "analyze returned: $($resp.Count) drift(s)"

Write-Host "STEP 7: show newest drifts"
$drifts2 = Invoke-Api GET "/drifts"
$items = @($drifts2.items)
if ($items.Count -eq 0) { Write-Host "No drifts found."; exit 0 }

$display = $items | Sort-Object date -Descending | Select-Object -First $MaxDrifts
$hasClassification = $false

$display | ForEach-Object {
  $commit = if ($_.commit_hash) { $_.commit_hash.Substring(0, [Math]::Min(8, $_.commit_hash.Length)) } else { "N/A" }
  $classification = if ($_.classification) { $_.classification } else { "" }
  if ($classification) { $hasClassification = $true }

  [PSCustomObject]@{
    Commit         = $commit
    DriftType      = $_.driftType
    Type           = $_.type
    Classification = $(if ($classification) { $classification } else { "(none)" })
    ReasonCodes    = $(if ($_.reason_codes) { ($_.reason_codes -join ",") } else { "(none)" })
  }
} | Format-Table -AutoSize

if (-not $hasClassification) {
  Write-Warning "No classification shown. Conformance classification commonly attaches when driftType == 'architecture'. Try another repo or increase MaxCommits."
}

Write-Host "DONE"
