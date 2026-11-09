# HiglowCloud

A low-cost hosting control-plane MVP inspired by Render and Vercel.

## Repository layout

- `frontend/`: React + Vite dashboard.
- `backend/`: FastAPI API and SQLAlchemy models.
- `docs/`: architecture and security notes.
- `render.yaml`: Render Blueprint for the control plane.

## Current MVP

- Project creation and listing.
- ZIP upload intake with basic archive path and size checks.
- Deployment metadata and redeploy records.
- API health endpoint.
- Render Blueprint for frontend, backend and PostgreSQL.

## Important deployment boundary

This is the **control plane**, not yet a complete public hosting runtime. ZIP uploads are validated and deployment records are created in `simulated` mode. Customer code is not executed. Real deployments require separately provisioned, isolated VPS build workers and runtime nodes.

Never execute customer code inside the public API service or expose the Docker socket to it.

## Render deployment

1. In Render, select **New → Blueprint**.
2. Connect this repository: `mikewach2006-crypto/Higlowcloud`.
3. Render should detect the root `render.yaml`.
4. Confirm the API service root directory is `backend`, and the static site root directory is `frontend`.
5. After services are created, confirm `FRONTEND_ORIGIN` and `VITE_API_URL` match the actual Render URLs.
6. Test the API health endpoint at `https://YOUR-API.onrender.com/health`.

The free Render PostgreSQL plan is for testing only; do not store production customer data on a temporary free database.

## Local development

Backend:
```bash
cd backend
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Not production-ready yet

Authentication, tenant isolation, GitHub App integration, persistent ZIP object storage, migrations, isolated build/runtime agents, custom domains, TLS automation, usage metering, billing, backups and operational monitoring remain to be implemented and security-tested before accepting customer workloads.
