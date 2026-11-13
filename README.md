# HiglowCloud

HiglowCloud is an email-authenticated cloud hosting control-plane MVP.

## Included in this MVP
- Email/password registration and login (no Google sign-in).
- Workspace and organization-scoped project records.
- GitHub HTTPS source references and ZIP upload intake.
- Deployment queue, history, cancellation and redeploy requests.
- Encrypted environment-variable storage.
- Custom-domain records and DNS verification tokens.
- PostgreSQL/Redis provisioning requests.
- Usage event ledger and workspace audit history.
- Platform admin overview, customer list and deployment list.
- Responsive React dashboard and FastAPI API.
- Render Blueprint for the dashboard, API and PostgreSQL metadata database.

## Important hosting boundary
The API does not execute customer code. Deployment requests remain queued until isolated build workers and runtime nodes are provisioned and connected. GitHub URLs are source references; private GitHub App integration and actual build execution are not connected yet. Domain records do not become live routes until an edge proxy and TLS automation are configured. Database requests do not provision instances until a database agent is connected.

Read docs/PRODUCT_SCOPE.md, docs/API_OVERVIEW.md and docs/INFRASTRUCTURE_ROADMAP.md before public launch.

## Render deployment
Deploy from the root render.yaml. The Blueprint generates SECRET_KEY and configures ADMIN_EMAILS for the platform operator. Confirm the actual service URLs match FRONTEND_ORIGIN and VITE_API_URL. The free Render database is for testing only. ZIP uploads currently use an ephemeral directory on the free web service; use a persistent disk or private object storage before depending on uploads across restarts.

## Local development
Backend:
    cd backend
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Frontend:
    cd frontend
    npm install
    npm run dev

## Production launch blockers
Before accepting customers, implement and test email verification, password reset, MFA, workspace invitations/RBAC, signed worker jobs, isolated builders and runtime sandboxes, persistent object storage, TLS edge routing, managed database provisioning, metering/billing, backups, abuse controls and security monitoring.


## Android builds (private beta)

HiglowCloud includes an on-demand Android build workspace at `/android-builds/`. Build jobs run on temporary GitHub-hosted Linux runners; they do not execute inside the Render API and do not require an always-on worker or the owner's computer.

The first supported targets are Nenva Call and unified Nenva debug APKs. Builds and artifacts stay private, artifacts expire after seven days, and the initial beta allows one platform build at a time. See [docs/ANDROID_BUILDS.md](docs/ANDROID_BUILDS.md) for GitHub App permissions, setup, limits and the first Nenva Call test.

This Android CI feature does not activate the separate web deployment runtime, custom-domain edge, or managed database provisioners described in the infrastructure roadmap.
