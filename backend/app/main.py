import io
import os
import zipfile
from pathlib import PurePosixPath
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import Project, Deployment
from .schemas import ProjectCreate, ProjectOut, DeploymentOut

# MVP only: replace create_all with Alembic migrations before production.
Base.metadata.create_all(bind=engine)
app = FastAPI(title="HiglowCloud API", version="0.1.0")
origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(CORSMiddleware, allow_origins=[origin, "http://localhost:5173"],
                   allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "higlowcloud-api"}

@app.get("/api/v1/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()

@app.post("/api/v1/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name or len(name) > 120:
        raise HTTPException(422, "Project name must be between 1 and 120 characters.")
    project = Project(name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@app.get("/api/v1/projects/{project_id}/deployments", response_model=list[DeploymentOut])
def list_deployments(project_id: int, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found.")
    return db.query(Deployment).filter_by(project_id=project_id).order_by(Deployment.created_at.desc()).all()

@app.post("/api/v1/deployments/upload", response_model=DeploymentOut, status_code=201)
async def upload_source(project_name: str = Form(...), source: UploadFile = File(...),
                        db: Session = Depends(get_db)):
    limit = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
    if not source.filename or not source.filename.lower().endswith(".zip"):
        raise HTTPException(415, "Upload a ZIP archive.")
    data = await source.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "ZIP exceeds the upload limit.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000:
                raise HTTPException(413, "Archive contains too many files.")
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or ".." in path.parts or entry.file_size > 50 * 1024 * 1024:
                    raise HTTPException(400, "Unsafe or oversized archive entry.")
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid ZIP archive.")
    name = project_name.strip()[:120]
    if not name:
        raise HTTPException(422, "Project name is required.")
    project = Project(name=name, source_type="zip_upload")
    db.add(project)
    db.flush()
    deployment = Deployment(project_id=project.id, status="accepted",
        source_name=source.filename[:255], mode="simulated",
        logs="ZIP validated and accepted. No customer code executed; isolated VPS build agent is not connected.")
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment

@app.post("/api/v1/deployments/{deployment_id}/redeploy", response_model=DeploymentOut)
def redeploy(deployment_id: int, db: Session = Depends(get_db)):
    old = db.get(Deployment, deployment_id)
    if not old:
        raise HTTPException(404, "Deployment not found.")
    item = Deployment(project_id=old.project_id, status="accepted", source_name=old.source_name,
                      mode="simulated", logs="Redeploy requested; execution remains simulated.")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
