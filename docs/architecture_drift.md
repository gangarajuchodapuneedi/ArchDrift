# Architecture Drift (Conformance)

## What is Architecture Drift vs Erosion
- **Drift**: Architecture changes (may be intentional). Needs review and ADR to capture the decision.
- **Erosion**: Violations (forbidden edges or cycles) that break intended architecture. Classified as negative.

## What "Conformance Mode" Means

Conformance mode compares your current code structure against a baseline snapshot and rules.

1. **Baseline**: A snapshot of module dependencies (edges) at a point in time.
2. **Mapping**: Files are mapped to modules using `module_map.json`.
3. **Compare**: Current edges vs baseline edges → see what changed.
4. **Rules**: `allowed_rules.json` defines which edges are allowed or forbidden.
5. **Classification**: Based on changes:
   - **Convergence**: Edge exists in both (no change).
   - **Divergence**: Edge added (new dependency).
   - **Absence**: Edge removed (dependency deleted).

## Files That Define "Intended Architecture"

These files live in `backend/architecture/`:

- **`module_map.json`**: Maps repo-relative paths to module IDs.
  - Example: `"src/ui"` → module `"ui"`, `"src/core"` → module `"core"`.
  - Files under these paths get mapped to their module.
- **`allowed_rules.json`**: Defines allowed module-to-module edges.
  - Example: `"ui" → "core"` is allowed, but `"core" → "ui"` might be forbidden.
  - Set `deny_by_default: true` to only allow listed edges.
- **`exceptions.json`**: Optional temporary exceptions (legacy).
  - Active exceptions are stored per-baseline in `baseline_exceptions.json`.

## Step-by-Step: Establish Baseline

Before you can run conformance analysis, you need a baseline with edges.

### Step 1: Edit module_map.json

Open `backend/architecture/module_map.json` and add your source directories:

```json
{
  "version": "1.0",
  "unmapped_module_id": "unmapped",
  "modules": [
    {"id": "ui", "roots": ["src/ui", "frontend/src/components"]},
    {"id": "core", "roots": ["src/core", "backend/utils"]},
    {"id": "api", "roots": ["src/api"]}
  ]
}
```

Make sure `roots` cover your actual source code paths (e.g., `src/`, `packages/`, `apps/`).

### Step 2: Generate Baseline

Call the API to create a draft baseline:

```bash
POST http://localhost:8000/baseline/generate
Content-Type: application/json

{
  "repo_path": "/path/to/your/repo",
  "config_dir": "/path/to/backend/architecture",
  "max_files": 2000,
  "max_file_bytes": 200000
}
```

Response includes `edge_count`. Check that `edge_count > 0`. If it's 0, your `module_map.json` roots don't match your source paths.

### Step 3: Check Baseline Edges

Look at the generated baseline file:

```
backend/data/baselines/<repo_id>/baseline_edges.json
```

This file should have edges like:
```json
{
  "version": "1.0",
  "edges": [
    {"from": "ui", "to": "core"},
    {"from": "api", "to": "core"}
  ]
}
```

If `edges` is empty `[]`, go back to Step 1 and fix your `module_map.json` roots.

### Step 4: Approve Baseline

Once you have edges, approve the baseline:

```bash
POST http://localhost:8000/baseline/approve
Content-Type: application/json

{
  "repo_path": "/path/to/your/repo",
  "approved_by": "your-name@example.com",
  "approval_note": "Initial baseline for conformance checking",
  "exceptions": []
}
```

The baseline is now "accepted" and ready for conformance comparison.

## Step-by-Step: Run Conformance Analysis

After baseline is approved, run analysis to detect drifts.

### Step 1: Set Conformance Mode

Set the environment variable before starting the backend:

**Windows (PowerShell):**
```powershell
$env:DRIFT_CLASSIFIER_MODE="conformance"
uvicorn main:app --reload
```

**Linux/Mac:**
```bash
export DRIFT_CLASSIFIER_MODE=conformance
uvicorn main:app --reload
```

### Step 2: Analyze Repository

Call the analyze endpoint:

```bash
POST http://localhost:8000/analyze-repo
Content-Type: application/json

{
  "repo_url": "https://github.com/your-org/your-repo.git",
  "max_commits": 50,
  "max_drifts": 5
}
```

This scans recent commits and compares current edges against the approved baseline.

### Step 3: Interpret Classification

Each drift has a `classification` field:

- **`negative`**: Forbidden edges or cycles were ADDED (erosion detected).
  - Action: Fix the dependency or add a time-boxed exception + ADR.
- **`positive`**: Forbidden edges or cycles were REMOVED (improvement).
  - Action: Review and update baseline if intentional.
- **`needs_review`**: Only allowed edges changed (architecture evolved).
  - Action: Write an ADR, review, update baseline/rules if accepted.
- **`no_change`**: No edge changes detected.
  - Action: No action needed, keep monitoring.
- **`unknown`**: Baseline or rules missing, or comparison failed.
  - Action: Generate/approve baseline or fix architecture config.

## Baseline Lifecycle

- **Draft baseline**: Generated edges from current repo (`baseline_edges.json`, `baseline_summary.json` with hash/counts).
- **Accepted baseline**: Approved via `baseline_meta.json` (approved_by/approved_at) plus any active exceptions (`baseline_exceptions.json`).
- **Why approval matters**: Conformance classification uses the accepted baseline as ground truth.

## Compare + Rule Checking
- Baseline vs current edges:
  - convergence (in both), divergence (added), absence (removed).
- Rule check:
  - forbidden edges = edges not allowed by rules, minus active exceptions.
- Cycles (optional): if cycle detection is enabled for the comparison, cycles added/removed are tracked.

## Classification (high level)
- **negative**: forbidden edges added (or cycles added if provided).
- **positive**: forbidden edges removed (or cycles removed if provided).
- **needs_review**: only allowed edges changed.
- **no_change**: no edge deltas.
- **unknown**: missing baseline or rules (or compare failed).

## Evidence Fields Explained (Conformance Mode)

Each drift in conformance mode includes these fields:

### Classification and Reason Codes
- **`classification`**: One of `positive`, `negative`, `needs_review`, `no_change`, `unknown`.
- **`reason_codes`**: Array explaining why classification is `unknown` (e.g., `BASELINE_MISSING`, `BASELINE_EMPTY`, `MAPPING_TOO_LOW`, `NO_SOURCE_FILES`).

### Edge Counts
- **`edges_added_count`**: Number of new module dependencies added.
- **`edges_removed_count`**: Number of module dependencies removed.
- **`forbidden_edges_added_count`**: Number of forbidden edges added (violations).
- **`forbidden_edges_removed_count`**: Number of forbidden edges removed (fixes).
- **`cycles_added_count`**: Number of dependency cycles added (if cycle detection enabled).
- **`cycles_removed_count`**: Number of dependency cycles removed (if cycle detection enabled).

### Hashes
- **`baseline_hash`**: SHA-256 hash of the baseline used for comparison.
- **`rules_hash`**: SHA-256 hash of the rules used for comparison.

### Evidence Preview
- **`evidence_preview`**: Top 10 edge changes showing:
  - `from_module` → `to_module`
  - `src_file`: Source file path
  - `import_text`: The import statement
  - `direction`: `"added"` or `"removed"`

**Important**: Commit message keywords are **not** used in conformance mode. Classification is based only on edge changes and rule violations.

## Operational Playbook
- **negative**: fix the dependency edge or add a time-boxed exception + ADR; then regenerate/approve baseline if intentional.
- **needs_review**: author an ADR, review, and update baseline/rules if the change is accepted.
- **unknown**: generate/approve baseline or fix architecture config.
- **no_change**: no action; keep monitoring.

## How to Get Signal (Troubleshooting)

If you're getting `unknown` classifications or empty evidence, use these steps.

### Check Baseline Health

Call the status endpoint to see baseline health:

```bash
GET http://localhost:8000/baseline/status?repo_path=/path/to/your/repo
```

The response includes a `baseline_health` object (if available):

```json
{
  "baseline_health": {
    "baseline_ready": false,
    "mapping_ready": false,
    "edge_count": 0,
    "included_files": 10,
    "unmapped_files": 7,
    "unmapped_ratio": 0.7,
    "unresolved_imports": 2,
    "top_unmapped_buckets": [
      {"bucket": "src/app", "count": 5},
      {"bucket": "packages/ui", "count": 2}
    ],
    "next_actions": [
      "Update module_map.json to cover your real source roots (e.g., src/, packages/) and regenerate baseline.",
      "Reduce unmapped files by adding/adjusting module_map.json prefixes for these buckets: src/app, packages/ui."
    ]
  }
}
```

### If `baseline_ready` is false

**Problem**: Baseline has 0 edges (`edge_count == 0`).

**What to do**:
1. Check `top_unmapped_buckets` to see which folders aren't mapped.
2. Update `module_map.json` to add roots for those buckets (e.g., `"src/app"`, `"packages/ui"`).
3. Regenerate baseline: `POST /baseline/generate`.
4. Verify `edge_count > 0` in the response.
5. Approve: `POST /baseline/approve`.

### If `mapping_ready` is false

**Problem**: Too many files are unmapped (`unmapped_ratio >= 0.50` or `included_files == 0`).

**What to do**:
1. Look at `top_unmapped_buckets` to see which folders need mapping.
2. Add those paths to `module_map.json` as new module roots or extend existing roots.
3. Regenerate baseline and check `unmapped_ratio` improves.
4. If `included_files == 0`, check that your source files have supported extensions (`.py`, `.js`, `.jsx`, `.ts`, `.tsx`).

### Other Common Issues

- **Rules too permissive**: Keep `deny_by_default: true` in `allowed_rules.json` and only list intended edges. Otherwise everything looks allowed.
- **Unsupported files**: Import extractors handle `.py`, `.js`, `.jsx`, `.ts`, `.tsx`. Other languages (Rust, Go, etc.) need an extractor to contribute edges.
- **High `unresolved_imports`**: If using TypeScript/JavaScript alias imports (e.g., `@/components/Button`), ensure `tsconfig.json` has `paths` and `baseUrl` configured. See MT_22 for alias support.
- **Unknown classification**: Baseline missing or rules missing/invalid. Rerun `/baseline/generate`, `/baseline/approve`, then `/analyze-repo` with `DRIFT_CLASSIFIER_MODE=conformance`.

