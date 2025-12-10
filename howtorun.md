# How to Run ArchDrift

This guide explains how to set up and run the ArchDrift application, including both backend and frontend components.

## Overview

ArchDrift consists of two main components:

- **Backend**: FastAPI server running on `http://localhost:8000`
- **Frontend**: React/Vite application running on `http://localhost:5173`

You'll need two terminal windows: one for the backend and one for the frontend.

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
   ```bash
   uvicorn main:app --reload
   ```

### Expected Output

You should see logs like:
```
Uvicorn running on http://127.0.0.1:8000
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
   ```bash
   npm run dev
   ```

### Expected Output

The terminal will show something like:
```
VITE vX.X.X  ready in XXXX ms

➜  Local:   http://localhost:5173/
```

✅ **Keep this second terminal open as well.** The browser will connect to this URL.

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
   # Start server
   uvicorn main:app --reload
   ```

3. **Run Frontend in Terminal 2:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Open the app in the browser** (usually `http://localhost:5173/`)

5. **Paste a repo URL** like:
   - `https://github.com/git/git`
   - `https://github.com/lokus-ai/lokus.git`

6. **Set Max commits and Max drifts**, click **"Analyze Repo"**

7. **Explore the drift tree on the left and the Decision Card on the right**
