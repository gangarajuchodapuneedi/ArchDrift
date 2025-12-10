# ArchDrift Backend

Lightweight FastAPI skeleton to power ArchDrift's architectural drift insights.

## Prerequisites
- Python 3.10+ (virtual environments recommended)
- Git (for GitPython to work)

## Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux
pip install --upgrade pip
pip install -r requirements.txt
```

## Run the server
```bash
cd backend
uvicorn main:app --reload
```

Visit `http://localhost:8000` and confirm:
- `/` returns `{"status": "ok", "app": "ArchDrift Backend"}`
- `/health` returns `{"status": "healthy"}`

## API Endpoints

### Health Check
- **GET** `/health` - Returns health status

### Debug Endpoints (Temporary)

#### List Commits
- **POST** `/debug/list-commits` - Clone/open a Git repository and list commit metadata

**Request Body:**
```json
{
  "repo_url": "https://github.com/user/repo.git",
  "max_commits": 20
}
```

**Response:**
```json
{
  "repo_path": "/path/to/cloned/repo",
  "commit_count": 20,
  "commits": [
    {
      "hash": "abc123...",
      "author": "John Doe",
      "email": "john@example.com",
      "date": "2024-01-15T10:30:00",
      "message": "Commit message"
    },
    ...
  ]
}
```

**Example Usage:**

Using curl:
```bash
curl -X POST "http://localhost:8000/debug/list-commits" \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/octocat/Hello-World.git", "max_commits": 10}'
```

Using PowerShell (Windows):
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug/list-commits" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"repo_url": "https://github.com/octocat/Hello-World.git", "max_commits": 10}'
```

**Note:** The first time you call this endpoint with a repository URL, it will clone the repository into `backend/.repos/`. Subsequent calls with the same URL will reuse the existing clone.

## Drift APIs (in-memory)

These endpoints provide access to architectural drift data. Currently using an in-memory store with sample data.

### List All Drifts
- **GET** `/drifts` - Returns all architectural drifts in chronological order

**Response:**
```json
{
  "items": [
    {
      "id": "drift-001",
      "date": "2024-01-15T10:30:00",
      "type": "negative",
      "title": "Database layer dependency introduced in API routes",
      "summary": "API route handlers now directly import database models, violating the layered architecture pattern.",
      "functionality": "API endpoints now bypass the service layer and access database models directly.",
      "advantage": null,
      "disadvantage": "Tight coupling between API and database layers makes testing and maintenance harder.",
      "root_cause": "Developer shortcut to avoid creating service layer methods.",
      "files_changed": [
        "api/routes.py",
        "api/users.py",
        "models/user.py"
      ],
      "commit_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
      "repo_url": "https://github.com/example/archdrift-demo"
    }
  ]
}
```

### Get Drift by ID
- **GET** `/drifts/{drift_id}` - Returns a single drift by its ID

**Response:**
```json
{
  "id": "drift-001",
  "date": "2024-01-15T10:30:00",
  "type": "negative",
  "title": "Database layer dependency introduced in API routes",
  "summary": "API route handlers now directly import database models, violating the layered architecture pattern.",
  "functionality": "API endpoints now bypass the service layer and access database models directly.",
  "advantage": null,
  "disadvantage": "Tight coupling between API and database layers makes testing and maintenance harder.",
  "root_cause": "Developer shortcut to avoid creating service layer methods.",
  "files_changed": [
    "api/routes.py",
    "api/users.py",
    "models/user.py"
  ],
  "commit_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
  "repo_url": "https://github.com/example/archdrift-demo"
}
```

**Error Response (404):**
```json
{
  "detail": "Drift not found"
}
```

**Example Usage:**

```powershell
# List all drifts
Invoke-RestMethod -Uri "http://localhost:8000/drifts"

# Get a specific drift
Invoke-RestMethod -Uri "http://localhost:8000/drifts/drift-001"
```

## Analyze Repo for Drifts (heuristic)

### Analyze Repository
- **POST** `/analyze-repo` - Analyzes a Git repository for architectural drifts using heuristic rules

This endpoint clones/opens a repository, examines recent commits, and converts them into Drift objects using simple keyword-based heuristics. This is an early version that does not use AI analysis yet.

**Request Body:**
```json
{
  "repo_url": "https://github.com/git/git",
  "max_commits": 50,
  "max_drifts": 5
}
```

**Response:**
```json
[
  {
    "id": "9a2fb147",
    "date": "2025-11-17T10:30:00",
    "type": "positive",
    "title": "refactor: improve code organization",
    "summary": "refactor: improve code organization",
    "functionality": "Functionality impacted (placeholder) based on commit message.",
    "advantage": "Likely positive architectural drift based on commit message keywords.",
    "disadvantage": null,
    "root_cause": null,
    "files_changed": [],
    "commit_hash": "9a2fb147f2c61d0cab52c883e7e26f5b7948e3ed",
    "repo_url": "https://github.com/git/git"
  }
]
```

**Example Usage:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/analyze-repo" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"repo_url": "https://github.com/git/git", "max_commits": 50, "max_drifts": 5}'
```

**Note:** The analysis uses simple keyword matching to classify drifts as "positive" or "negative". Commits containing words like "refactor", "cleanup", "optimize", "improve", "scale", or "migrate" are classified as positive. All other commits are classified as negative (this is a placeholder that will be enhanced with AI analysis in future versions).

