# How to Run ArchDrift

This guide explains how to set up and run the ArchDrift application, including both backend and frontend components.

## Overview

ArchDrift consists of two main components:

- **Backend**: FastAPI server running on `http://localhost:8000`
- **Frontend**: React/Vite application running on `http://localhost:5173`

You'll need two terminal windows: one for the backend and one for the frontend.

## Conformance Quickstart

ArchDrift supports two modes: **keywords mode** (legacy) and **conformance mode** (recommended). Conformance mode compares code structure against a baseline and rules.

### Enable Conformance Mode

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

### Generate and Approve Baseline

Before analyzing, you need a baseline with edges:

1. **Edit `backend/architecture/module_map.json`** to map your source paths to modules.
2. **Generate baseline:**
   ```bash
   POST http://localhost:8000/baseline/generate
   {
     "repo_path": "/path/to/your/repo"
   }
   ```
3. **Check `edge_count`** in response. If 0, fix `module_map.json` and regenerate.
4. **Approve baseline:**
   ```bash
   POST http://localhost:8000/baseline/approve
   {
     "repo_path": "/path/to/your/repo",
     "approved_by": "your-name@example.com"
   }
   ```

### Check Baseline Health

If you get `unknown` classifications or empty evidence:

```bash
GET http://localhost:8000/baseline/status?repo_path=/path/to/your/repo
```

Look for `baseline_health`:
- If `baseline_ready = false`: Baseline has 0 edges → fix `module_map.json` and regenerate.
- If `mapping_ready = false`: Too many unmapped files → add missing paths to `module_map.json`.
- Check `next_actions` for specific guidance.

See [Architecture Drift Documentation](docs/architecture_drift.md) for detailed steps and troubleshooting.

**Note**: Keywords mode remains supported for legacy workflows. Set `DRIFT_CLASSIFIER_MODE=keywords` (or omit) to use commit message keyword detection.

## Conformance Mode Quickstart (Windows)

For beginners: use the bootstrap script to get classification badges without manual setup.

### Step 1: Start Backend in Conformance Mode

In PowerShell (Terminal 1):
```powershell
cd backend
$env:DRIFT_CLASSIFIER_MODE="conformance"
python -m uvicorn main:app --reload --port 8000
```

### Step 2: Run Bootstrap Script

In a new PowerShell terminal (Terminal 2, same repo root):
```powershell
cd backend
.\tools\bootstrap_conformance.ps1 -Port 8000
```

The script will:
- Check backend health
- Auto-discover or use default repo URL
- Clone/open repo and get local path
- Generate baseline if missing
- Auto-approve baseline
- Run analysis
- Display results table

### Step 3: View Results

Start frontend and refresh browser to see classification badges (Needs Review / Unknown) in the drift timeline.

**Custom Options:**
```powershell
# Use specific repo
.\tools\bootstrap_conformance.ps1 -RepoUrl "https://github.com/user/repo" -Port 8000

# Adjust analysis parameters
.\tools\bootstrap_conformance.ps1 -MaxCommits 30 -MaxDrifts 10 -Port 8000

# Skip auto-approval (manual approval required)
.\tools\bootstrap_conformance.ps1 -AutoApprove $false -Port 8000
```

## 1. Running the Backend (Terminal 1)

### Setup Steps

1. **Open a new terminal in VS Code**
   - Terminal → New Terminal

2. **Navigate to the backend folder**
   ```bash
   cd backend
   ```

3. **Create and activate a virtual environment** (Recommended)

   On Windows (PowerShell / Command Prompt):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

4. **Install backend dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start the backend server**
   
   For localhost only:
   ```bash
   uvicorn main:app --reload
   ```
   
   For network access (accessible from other devices on your network):
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Expected Output

For localhost:
```
Uvicorn running on http://127.0.0.1:8000
```

For network access:
```
Uvicorn running on http://0.0.0.0:8000
```

✅ **Keep this terminal open and running.** The frontend will call this backend API.

## 2. Running the Frontend (Terminal 2)

### Setup Steps

1. **Open another terminal in VS Code**
   - Terminal → New Terminal
   - (You will now have two terminals: one for backend, one for frontend)

2. **Navigate to the frontend folder**
   ```bash
   cd frontend
   ```

3. **Install frontend dependencies**
   ```bash
   npm install
   ```

4. **Start the frontend dev server**
   
   For localhost only:
   ```bash
   npm run dev
   ```
   
   For network access (accessible from other devices on your network):
   ```bash
   npm run dev -- --host
   ```

### Expected Output

For localhost:
```
VITE vX.X.X  ready in XXXX ms

➜  Local:   http://localhost:5173/
```

For network access:
```
VITE vX.X.X  ready in XXXX ms

➜  Local:   http://localhost:5173/
➜  Network: http://192.168.x.x:5173/
```

✅ **Keep this second terminal open as well.** The browser will connect to this URL.

**Note:** When accessing via network IP, the frontend will automatically detect the hostname and connect to the backend on the same IP address (port 8000).

## 3. Opening the App in the Browser

Once `npm run dev` is running, open your browser and navigate to:

```
http://localhost:5173/
```

### What You Should See

The ArchDrift UI with:

- **Title**: ArchDrift – Architectural Drift Map (Prototype)
- **Input box** for Repo URL
- **Inputs** for Max commits and Max drifts
- **Analyze Repo** button
- **Repo Health** bar (after analysis)
- **Drift tree** on the left and a **detail panel** on the right

## 6. Architecture drift modes

There are two classifier modes:

- **keywords** (default/legacy): sentiment from commit-message keywords (positive/negative). No conformance evidence.
- **conformance**: deterministic, config-driven classification (positive/negative/needs_review/unknown/no_change) using architecture config + baselines. Commit messages are not read.

### Running in keyword mode (default)
No env var required (or set explicitly):
```bash
set DRIFT_CLASSIFIER_MODE=keywords
uvicorn main:app
```

### Running in conformance mode
```bash
set DRIFT_CLASSIFIER_MODE=conformance
uvicorn main:app
```

Architecture config (backend/architecture/):
- `module_map.json`: maps repo paths to module IDs.
- `allowed_rules.json`: allowed module-to-module edges.
- `exceptions.json`: optional temporary exceptions.

Baseline lifecycle (stored under `backend/data/baselines/<repo_id>/`):
- Generate draft baseline: `POST /baseline/generate`
- Approve baseline: `POST /baseline/approve`
- Check status: `GET /baseline/status`

Analyze a repo after baseline is accepted:
```bash
POST /analyze-repo
{
  "repo_url": "<git-url>",
  "max_commits": 50,
  "max_drifts": 5
}
```

Classification (high level):
- negative: forbidden edges added (cycles if enabled)
- positive: forbidden edges removed
- needs_review: only allowed edges changed
- no_change: no edge deltas
- unknown: baseline or rules missing

Evidence fields (conformance mode):
- `classification`, `reason_codes`
- edge counts: `edges_added_count`, `edges_removed_count`
- forbidden counts: `forbidden_edges_added_count`, `forbidden_edges_removed_count`
- cycles counts: `cycles_added_count`, `cycles_removed_count`
- hashes: `baseline_hash`, `rules_hash`
- `evidence_preview` (top edge changes)

Troubleshooting:
- `classification=unknown`: baseline or rules missing.
- Counts are zero but changes expected: `module_map` may not map the paths; or file type not supported by import extractors (supported: .py, .js, .jsx, .ts, .tsx).
- Unsupported languages (e.g., Rust/Go) are not parsed unless an extractor is implemented.
- Baseline shows 0 edges: widen `module_map.json` roots to include your source dirs, regenerate via `/baseline/generate`, then `/baseline/approve`.

## 4. How to Use the Prototype

### Example Repositories

Use these public repos to see the analyzer in action:

- **Git source repo** (large, mature project)
  ```
  https://github.com/git/git
  ```

- **Lokus project** (good for UI/API drifts)
  ```
  https://github.com/lokus-ai/lokus.git
  ```

### Step-by-Step Usage

1. **In the Repo URL field**, paste one of:
   - `https://github.com/git/git`
   - or `https://github.com/lokus-ai/lokus.git`

2. **Set parameters:**
   - **Max commits** – for example: `30`
   - **Max drifts** – for example: `5`

3. **Click "Analyze Repo"**

4. **Wait a few seconds** while:
   - **The backend:**
     - Pulls commit history (for the chosen window)
     - Classifies drifts (type, sentiment, teams)
     - Generates text for summary / functionality / disadvantage / root cause / recommended actions
   - **The frontend:**
     - Updates the Repo Health bar
     - Draws the drift tree on the left
     - Shows a Decision Card for the selected drift on the right

## 5. What You Should See After Analysis

### 1. Repo Health (Top)

Example:
```
Repo Health
In this analysis window: 5 drifts (4 positive, 1 negative)
Most affected area: API Contract
Most impacted team: Frontend
```

This is the **Mirror at repo level** – what's happening overall in this slice of history.

### 2. Drift Tree (Left Side)

For each drift, you'll see:

- **Date** (from commit timestamp)
- **Sentiment**: positive / negative
- **Drift type**: e.g. Architecture, API Contract, UI / UX, Schema / DB
- **Teams**: e.g. Backend, Frontend, DB, Shared
- **Commit title**: e.g. "Add image viewer and fix file creation in scoped views (#196)"

Clicking one of these nodes/cards changes the detail panel on the right.

### 3. Drift Detail / Decision Card (Right Side)

For the selected drift, you should see something like:

```
Add image viewer and fix file creation in scoped views (#196)
negative
November 14, 2025 at 01:00 AM

Impact: High
Affects: Maintainability, Testability

Summary
This change affects user interface or user experience: Add image viewer and fix file creation in scoped views (#196)

Functionality
This change impacts functionality in the src-tauri, src area(s), based on the changed files.

Disadvantage
UI/UX drift may create inconsistent user experiences across different parts of the application.

Root Cause
The drift was detected because UI/UX-related files changed in ways that may affect user experience consistency.

Recommended Actions
- Review UI/UX changes for consistency with design system guidelines.
- Ensure user experience remains consistent across different parts of the application.
- Document any intentional design deviations and their rationale.

Files Changed
- src-tauri/src/handlers/files.rs
- src-tauri/src/main.rs
- src/components/CommandPalette.jsx
- ...

Commit: 2d1444a9aa9a30d7c3a0a2d81e3185c770029fde
Repository: https://github.com/lokus-ai/lokus.git
```

### 4. Copy as Ticket Feature

You'll see a **"Copy as ticket"** button:

- Clicking it copies a Markdown body containing:
  - **Mirror section** (what happened)
  - **Mentor section** (impact + recommended actions)
- You can paste this directly into Jira / GitHub Issues / any tracker.

## Summary

### Quick Start Checklist

1. **Open the project folder in VS Code**

2. **Run Backend in Terminal 1:**
   ```bash
   cd backend
   # Create & activate venv
   python -m venv .venv
   .venv\Scripts\activate
   # Install dependencies
   pip install -r requirements.txt
   # Start server (localhost only)
   uvicorn main:app --reload
   # OR for network access:
   # uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Run Frontend in Terminal 2:**
   ```bash
   cd frontend
   npm install
   # Start dev server (localhost only)
   npm run dev
   # OR for network access:
   # npm run dev -- --host
   ```

4. **Open the app in the browser** (usually `http://localhost:5173/`)

5. **Paste a repo URL** like:
   - `https://github.com/git/git`
   - `https://github.com/lokus-ai/lokus.git`

6. **Set Max commits and Max drifts**, click **"Analyze Repo"**

7. **Explore the drift tree on the left and the Decision Card on the right**
