"""Entry point for the ArchDrift FastAPI application."""

import os
import shutil

# Configure GitPython to find git executable
# Try to find git in PATH first
git_path = shutil.which("git")
if not git_path:
    # Try common Git installation paths on Windows
    common_paths = [
        r"D:\Git\cmd\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Users\{}\AppData\Local\Programs\Git\cmd\git.exe".format(os.getenv("USERNAME", "")),
    ]
    for path in common_paths:
        if os.path.exists(path):
            git_path = path
            break

if git_path:
    os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = git_path
    import git
    git.refresh(path=git_path)
else:
    raise RuntimeError(
        "Git executable not found. Please install Git from https://git-scm.com/download/win "
        "or set GIT_PYTHON_GIT_EXECUTABLE environment variable to the path of git.exe"
    )

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router

app = FastAPI(title="ArchDrift Backend", version="0.1.0")

# Allow local frontends (React dev servers) to access the API during development.
origins = [ "*"
#     "http://localhost:5173",
#     "http://127.0.0.1:5173",
# 
]
#  explain why we allow all origins: we allow all origins because we are developing the backend and the frontend in the same machine
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include versioned API routes.
app.include_router(api_router)


@app.get("/")
async def root() -> dict:
    """
    Simple heartbeat endpoint to confirm the API is online.

    Returns:
        dict: App metadata payload.
    """
    return {"status": "ok", "app": "ArchDrift Backend"}

